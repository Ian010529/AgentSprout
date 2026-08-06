from __future__ import annotations

import shutil
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import as_utc, canonical_hash, keyed_hash, utc_now
from app.db.models import (
    Agent,
    AgentVersion,
    AuditEvent,
    DemoSession,
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationRun,
    IdempotencyRecord,
    KnowledgeDocument,
    TeacherReview,
)
from app.db.readiness import RuntimeResources
from app.db.vector import COLLECTION_NAME
from app.domain.contracts import (
    ApproveVersion,
    ComparisonCase,
    ComparisonCategory,
    ComparisonSide,
    NextVersion,
    RequestChanges,
    ReviewDecisionResponse,
    TeacherReviewView,
    VersionComparison,
    VersionDetail,
)
from app.domain.enums import DocumentStatus, EvaluationCategory, EvaluationState, Role, VersionState
from app.domain.errors import ApiError
from app.services.agents import get_version


def _require_role(session: DemoSession, role: Role) -> None:
    if session.role != role.value:
        raise ApiError(403, f"{role.value}_ROLE_REQUIRED", f"Switch to {role.value.title()} mode.")


def _evaluation(db: Session, run_id: str, version_id: str) -> EvaluationRun:
    run = db.get(EvaluationRun, run_id)
    if run is None or run.version_id != version_id:
        raise ApiError(409, "EVALUATION_VERSION_MISMATCH", "Choose an evaluation for this version.")
    if run.state != EvaluationState.COMPLETED.value:
        raise ApiError(409, "EVALUATION_NOT_COMPLETE", "Wait for the evaluation to complete.")
    return run


def _review_view(review: TeacherReview) -> TeacherReviewView:
    return TeacherReviewView(
        id=review.id,
        evaluation_run_id=review.evaluation_run_id,
        decision=review.decision,  # pyright: ignore[reportArgumentType]
        feedback=review.feedback,
        created_at=as_utc(review.created_at),
    )


def request_changes(
    db: Session, session: DemoSession, version_id: str, payload: RequestChanges
) -> ReviewDecisionResponse:
    _require_role(session, Role.TEACHER)
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    if version.state != VersionState.IN_REVIEW.value:
        raise ApiError(409, "INVALID_VERSION_TRANSITION", "Only an in-review version can change.")
    _evaluation(db, payload.evaluation_run_id, version.id)
    now = utc_now()
    version.state = VersionState.CHANGES_REQUESTED.value
    version.updated_at = now
    review = TeacherReview(
        id=str(uuid4()),
        version_id=version.id,
        evaluation_run_id=payload.evaluation_run_id,
        session_id=session.id,
        decision="REQUEST_CHANGES",
        feedback=payload.feedback,
        created_at=now,
    )
    db.add_all(
        [
            review,
            AuditEvent(
                id=str(uuid4()),
                session_id=session.id,
                actor_type="DEMO_SESSION",
                action="CHANGES_REQUESTED",
                target_type="AGENT_VERSION",
                target_id=version.id,
                result="SUCCESS",
                created_at=now,
            ),
        ]
    )
    db.commit()
    return ReviewDecisionResponse(
        version=get_version(db, session, version.id), review=_review_view(review)
    )


def _copy_document_snapshot(
    resources: RuntimeResources,
    source: KnowledgeDocument,
    target_version: AgentVersion,
    agent_id: str,
) -> KnowledgeDocument:
    upload_root = resources.settings.uploads_path.resolve()
    source_path = Path(source.storage_path).resolve()
    try:
        source_path.relative_to(upload_root)
    except ValueError as error:
        raise ApiError(
            500, "KNOWLEDGE_COPY_FAILED", "The source snapshot is unavailable."
        ) from error
    document_id = str(uuid4())
    target_dir = (upload_root / document_id).resolve()
    target_dir.relative_to(upload_root)
    target_dir.mkdir(parents=True, exist_ok=False)
    target_path = target_dir / f"source.{source.extension}"
    try:
        shutil.copy2(source_path, target_path)
        collection = resources.chroma.get_collection(COLLECTION_NAME)
        payload = collection.get(
            where={"document_id": source.id},
            include=["documents", "metadatas", "embeddings"],
        )
        old_ids = list(payload["ids"])
        documents = payload["documents"]
        metadatas = cast(list[dict[str, Any]] | None, payload["metadatas"])
        embeddings = payload["embeddings"]
        if (
            not old_ids
            or documents is None
            or metadatas is None
            or embeddings is None
            or len(old_ids) != source.chunk_count
        ):
            raise ValueError("source vectors incomplete")
        new_ids = [f"{document_id}:{index}" for index in range(len(old_ids))]
        copied_metadata: list[dict[str, Any]] = []
        for metadata in metadatas:
            copied = dict(metadata)
            copied.update(
                agent_id=agent_id,
                version_id=target_version.id,
                document_id=document_id,
            )
            copied_metadata.append(copied)
        collection.upsert(
            ids=new_ids,
            documents=documents,
            embeddings=cast(Any, embeddings),
            metadatas=cast(Any, copied_metadata),
        )
    except Exception as error:
        if target_path.exists():
            target_path.unlink()
        if target_dir.exists():
            target_dir.rmdir()
        raise ApiError(
            500, "KNOWLEDGE_COPY_FAILED", "The source snapshot could not copy."
        ) from error
    return KnowledgeDocument(
        id=document_id,
        version_id=target_version.id,
        original_filename=source.original_filename,
        media_type=source.media_type,
        extension=source.extension,
        byte_size=source.byte_size,
        sha256=source.sha256,
        storage_path=str(target_path),
        status=DocumentStatus.READY.value,
        page_count=source.page_count,
        chunk_count=source.chunk_count,
        embedding_model=source.embedding_model,
        error_code=None,
        is_active=1,
        created_at=utc_now(),
        ready_at=utc_now(),
        retired_at=None,
    )


def create_next_version(
    db: Session,
    resources: RuntimeResources,
    session: DemoSession,
    source_version_id: str,
    payload: NextVersion,
    idempotency_key: str | None,
) -> VersionDetail:
    _require_role(session, Role.STUDENT)
    if not idempotency_key or not 8 <= len(idempotency_key) <= 200:
        raise ApiError(400, "IDEMPOTENCY_KEY_REQUIRED", "A valid next-version key is required.")
    source = db.get(AgentVersion, source_version_id)
    if source is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    if source.state not in {
        VersionState.CHANGES_REQUESTED.value,
        VersionState.APPROVED.value,
        VersionState.PUBLISHED.value,
    }:
        raise ApiError(409, "INVALID_VERSION_TRANSITION", "This version cannot start a Draft.")
    agent = db.get(Agent, source.agent_id)
    if agent is None:
        raise ApiError(404, "AGENT_NOT_FOUND", "The Agent was not found.")
    scope = f"NEXT_VERSION:{source.id}"
    key_hash = keyed_hash(resources.settings, "idempotency", idempotency_key)
    request_hash = canonical_hash(payload.model_dump())
    replay = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.session_id == session.id,
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key_hash == key_hash,
        )
    )
    if replay is not None and as_utc(replay.expires_at) > utc_now():
        if replay.request_hash != request_hash:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This next-version key was reused.")
        return VersionDetail.model_validate_json(replay.response_body)
    if agent.current_draft_version_id is not None:
        raise ApiError(409, "DRAFT_ALREADY_EXISTS", "Continue the existing Draft version.")
    source_document = (
        db.get(KnowledgeDocument, source.active_document_id) if source.active_document_id else None
    )
    if source_document is None or source_document.status != DocumentStatus.READY.value:
        raise ApiError(409, "KNOWLEDGE_NOT_READY", "The source version has no Ready knowledge.")
    now = utc_now()
    next_number = (
        max(
            db.scalars(select(AgentVersion.version_number).where(AgentVersion.agent_id == agent.id))
        )
        + 1
    )
    version = AgentVersion(
        id=str(uuid4()),
        agent_id=agent.id,
        version_number=next_number,
        state=VersionState.DRAFT.value,
        project_name=source.project_name,
        problem_to_solve=source.problem_to_solve,
        intended_users=source.intended_users,
        audience_age=source.audience_age,
        success_goal=source.success_goal,
        welcome_message=source.welcome_message,
        tone=source.tone,
        response_length=source.response_length,
        custom_instructions=source.custom_instructions,
        what_changed=payload.what_changed,
        why_changed=payload.why_changed,
        source_version_id=source.id,
        active_document_id=None,
        submitted_at=None,
        approved_at=None,
        published_at=None,
        withdrawn_at=None,
        created_at=now,
        updated_at=now,
    )
    document = _copy_document_snapshot(resources, source_document, version, agent.id)
    version.active_document_id = document.id
    agent.current_draft_version_id = version.id
    agent.updated_at = now
    db.add_all([version, document])
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        resources.chroma.get_collection(COLLECTION_NAME).delete(where={"document_id": document.id})
        Path(document.storage_path).unlink(missing_ok=True)
        Path(document.storage_path).parent.rmdir()
        raise ApiError(
            409, "DRAFT_ALREADY_EXISTS", "Continue the existing Draft version."
        ) from error
    response = get_version(db, session, version.id)
    db.add_all(
        [
            IdempotencyRecord(
                id=str(uuid4()),
                session_id=session.id,
                scope=scope,
                key_hash=key_hash,
                request_hash=request_hash,
                response_status=201,
                response_body=response.model_dump_json(),
                created_at=now,
                expires_at=now + timedelta(hours=resources.settings.idempotency_hours),
            ),
            AuditEvent(
                id=str(uuid4()),
                session_id=session.id,
                actor_type="DEMO_SESSION",
                action="NEXT_VERSION_CREATED",
                target_type="AGENT_VERSION",
                target_id=version.id,
                result="SUCCESS",
                created_at=now,
            ),
        ]
    )
    db.commit()
    return response


def approve_version(
    db: Session,
    resources: RuntimeResources,
    session: DemoSession,
    version_id: str,
    payload: ApproveVersion,
) -> ReviewDecisionResponse:
    _require_role(session, Role.TEACHER)
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    if version.state != VersionState.IN_REVIEW.value:
        raise ApiError(409, "INVALID_VERSION_TRANSITION", "Only an in-review version can approve.")
    run = _evaluation(db, payload.evaluation_run_id, version.id)
    baseline = (
        resources.settings.online_model,
        resources.settings.judge_model,
        resources.settings.embedding_model,
        resources.settings.moderation_model,
    )
    if (
        not run.release_eligible
        or (
            run.online_model,
            run.judge_model,
            run.embedding_model,
            run.moderation_model,
        )
        != baseline
    ):
        raise ApiError(409, "RELEASE_GATE_FAILED", "Choose an eligible current-baseline run.")
    now = utc_now()
    version.state = VersionState.APPROVED.value
    version.approved_at = now
    version.updated_at = now
    review = TeacherReview(
        id=str(uuid4()),
        version_id=version.id,
        evaluation_run_id=run.id,
        session_id=session.id,
        decision="APPROVE",
        feedback=None,
        created_at=now,
    )
    db.add_all(
        [
            review,
            AuditEvent(
                id=str(uuid4()),
                session_id=session.id,
                actor_type="DEMO_SESSION",
                action="VERSION_APPROVED",
                target_type="AGENT_VERSION",
                target_id=version.id,
                result="SUCCESS",
                created_at=now,
            ),
        ]
    )
    db.commit()
    return ReviewDecisionResponse(
        version=get_version(db, session, version.id), review=_review_view(review)
    )


def compare_versions(
    db: Session,
    session: DemoSession,
    left_version_id: str,
    right_version_id: str,
    left_run_id: str,
    right_run_id: str,
) -> VersionComparison:
    _require_role(session, Role.TEACHER)
    left_version = db.get(AgentVersion, left_version_id)
    right_version = db.get(AgentVersion, right_version_id)
    if (
        left_version is None
        or right_version is None
        or left_version.agent_id != right_version.agent_id
    ):
        raise ApiError(404, "VERSION_NOT_FOUND", "Comparable versions were not found.")
    left = _evaluation(db, left_run_id, left_version.id)
    right = _evaluation(db, right_run_id, right_version.id)
    if (
        left.suite_version,
        left.online_model,
        left.judge_model,
        left.embedding_model,
    ) != (
        right.suite_version,
        right.online_model,
        right.judge_model,
        right.embedding_model,
    ):
        raise ApiError(409, "COMPARISON_BASELINE_MISMATCH", "Choose matching evaluation baselines.")
    rows: dict[str, dict[str, tuple[EvaluationCaseResult, EvaluationCase]]] = {}
    for label, run in (("left", left), ("right", right)):
        rows[label] = {
            case.case_key: (result, case)
            for result, case in db.execute(
                select(EvaluationCaseResult, EvaluationCase)
                .join(EvaluationCase)
                .where(EvaluationCaseResult.evaluation_run_id == run.id)
            )
        }
    if set(rows["left"]) != set(rows["right"]):
        raise ApiError(409, "COMPARISON_CASE_MISMATCH", "Evaluation case sets do not match.")
    categories: dict[str, dict[str, int]] = defaultdict(
        lambda: {"left_passed": 0, "left_total": 0, "right_passed": 0, "right_total": 0}
    )
    cases: list[ComparisonCase] = []
    for key in sorted(rows["left"]):
        left_result, case = rows["left"][key]
        right_result, _ = rows["right"][key]
        category = categories[case.category]
        category["left_total"] += 1
        category["right_total"] += 1
        category["left_passed"] += left_result.passed
        category["right_passed"] += right_result.passed
        transition = (
            "IMPROVED"
            if not left_result.passed and right_result.passed
            else "REGRESSED"
            if left_result.passed and not right_result.passed
            else "UNCHANGED"
        )
        cases.append(
            ComparisonCase(
                case_key=key,
                category=EvaluationCategory(case.category),
                left_passed=bool(left_result.passed),
                right_passed=bool(right_result.passed),
                transition=transition,
            )
        )
    latency = {
        label: sum(result.latency_ms for result, _case in side.values())
        for label, side in rows.items()
    }
    return VersionComparison(
        left=ComparisonSide(
            version_id=left_version.id,
            version_number=left_version.version_number,
            run_id=left.id,
            release_eligible=bool(left.release_eligible),
        ),
        right=ComparisonSide(
            version_id=right_version.id,
            version_number=right_version.version_number,
            run_id=right.id,
            release_eligible=bool(right.release_eligible),
        ),
        deltas={
            "grounded_pass_rate": float(right.grounded_pass_rate or 0)
            - float(left.grounded_pass_rate or 0),
            "age_average": float(right.age_average or 0) - float(left.age_average or 0),
            "instruction_average": float(right.instruction_average or 0)
            - float(left.instruction_average or 0),
            "latency_ms": latency["right"] - latency["left"],
            "input_tokens": right.input_tokens - left.input_tokens,
            "output_tokens": right.output_tokens - left.output_tokens,
            "estimated_cost_usd": float(right.estimated_cost_usd) - float(left.estimated_cost_usd),
        },
        categories=[
            ComparisonCategory(
                category=EvaluationCategory(name),
                **values,
                passed_delta=values["right_passed"] - values["left_passed"],
            )
            for name, values in sorted(categories.items())
        ],
        cases=cases,
    )
