from __future__ import annotations

import hmac
import math
import secrets
import shutil
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import as_utc, canonical_hash, keyed_hash, utc_now
from app.db.models import (
    Agent,
    AgentVersion,
    AuditEvent,
    ChatRun,
    DemoSession,
    IdempotencyRecord,
    KnowledgeDocument,
    RateLimitBucket,
    TeacherReview,
)
from app.db.readiness import RuntimeResources
from app.db.vector import COLLECTION_NAME
from app.domain.contracts import (
    ChatResultView,
    FixedSampleResponse,
    PublicAgentView,
    PublicRunCreate,
    PublicRunCreateResponse,
    PublicRunView,
    PublishResponse,
    PublishVersion,
    ResetResponse,
)
from app.domain.enums import (
    ChatPhase,
    ChatResultType,
    ChatStatus,
    DocumentStatus,
    Role,
    VersionState,
)
from app.domain.errors import ApiError
from app.services.chat import process_public_chat
from app.services.chat_queries import PHASE_COPY
from app.services.chat_safety import SAFE_PRIVACY_ANSWER, detect_pii
from app.services.public_store import PublicMemoryRun, TransientStore

PUBLIC_HOUR_SCOPE = "PUBLIC_CHAT_HOUR"
PUBLIC_DAY_SCOPE = "PUBLIC_CHAT_DAY"
SOURCE_ATTRIBUTION = {
    "title": "Ocean Literacy, Version 3.2 (2024)",
    "author": "NOAA",
    "license": "CC0 Public Domain",
    "source_url": "https://repository.library.noaa.gov/view/noaa/67228",
}


def _teacher(session: DemoSession) -> None:
    if session.role != Role.TEACHER.value:
        raise ApiError(403, "TEACHER_ROLE_REQUIRED", "Switch to Teacher mode.")


def _valid_key(value: str | None, label: str) -> str:
    if not value or not 8 <= len(value) <= 200:
        raise ApiError(400, "IDEMPOTENCY_KEY_REQUIRED", f"A valid {label} key is required.")
    return value


def _approval_review(db: Session, version_id: str) -> TeacherReview:
    review = db.scalar(
        select(TeacherReview)
        .where(
            TeacherReview.version_id == version_id,
            TeacherReview.decision == "APPROVE",
        )
        .order_by(TeacherReview.created_at.desc())
    )
    if review is None:
        raise ApiError(409, "APPROVAL_EVIDENCE_MISSING", "Approval evidence is unavailable.")
    return review


def publish_version(
    db: Session,
    resources: RuntimeResources,
    session: DemoSession,
    version_id: str,
    payload: PublishVersion,
    idempotency_key: str | None,
) -> PublishResponse:
    _teacher(session)
    raw_key = _valid_key(idempotency_key, "publication idempotency")
    scope = f"PUBLISH:{version_id}"
    key_hash = keyed_hash(resources.settings, "idempotency", raw_key)
    request_hash = canonical_hash(payload.model_dump())
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.session_id == session.id,
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key_hash == key_hash,
        )
    )
    if existing is not None and as_utc(existing.expires_at) > utc_now():
        if existing.request_hash != request_hash:
            raise ApiError(409, "IDEMPOTENCY_KEY_REUSED", "This publication key was reused.")
        return PublishResponse.model_validate_json(existing.response_body)

    version = db.get(AgentVersion, version_id)
    if version is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    if version.state != VersionState.APPROVED.value:
        raise ApiError(409, "VERSION_NOT_APPROVED", "Only an Approved version can publish.")
    document = (
        db.get(KnowledgeDocument, version.active_document_id)
        if version.active_document_id
        else None
    )
    if document is None or document.status != DocumentStatus.READY.value:
        raise ApiError(409, "KNOWLEDGE_NOT_READY", "Published knowledge must be Ready.")
    agent = db.get(Agent, version.agent_id)
    if agent is None or agent.deleted_at is not None:
        raise ApiError(404, "AGENT_NOT_FOUND", "The Agent was not found.")
    conflict = db.scalar(select(Agent).where(Agent.slug == payload.slug, Agent.id != agent.id))
    if conflict is not None:
        raise ApiError(409, "PUBLIC_SLUG_TAKEN", "Choose another public address.")

    approval = _approval_review(db, version.id)
    now = utc_now()
    version.state = VersionState.PUBLISHED.value
    version.published_at = now
    version.withdrawn_at = None
    version.updated_at = now
    agent.slug = payload.slug
    agent.published_version_id = version.id
    agent.display_name = version.project_name
    agent.updated_at = now
    review = TeacherReview(
        id=str(uuid4()),
        version_id=version.id,
        evaluation_run_id=approval.evaluation_run_id,
        session_id=session.id,
        decision="PUBLISH",
        feedback=None,
        created_at=now,
    )
    response = PublishResponse(
        slug=payload.slug,
        public_path=f"/p/{payload.slug}",
        version_number=version.version_number,
    )
    db.add_all(
        [
            review,
            IdempotencyRecord(
                id=str(uuid4()),
                session_id=session.id,
                scope=scope,
                key_hash=key_hash,
                request_hash=request_hash,
                response_status=200,
                response_body=response.model_dump_json(),
                created_at=now,
                expires_at=now + timedelta(hours=resources.settings.idempotency_hours),
            ),
            AuditEvent(
                id=str(uuid4()),
                session_id=session.id,
                actor_type="DEMO_SESSION",
                action="VERSION_PUBLISHED",
                target_type="AGENT_VERSION",
                target_id=version.id,
                result="SUCCESS",
                created_at=now,
            ),
        ]
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ApiError(409, "PUBLIC_SLUG_TAKEN", "Choose another public address.") from error
    return response


def withdraw_version(
    db: Session,
    resources: RuntimeResources,
    session: DemoSession,
    version_id: str,
    idempotency_key: str | None,
) -> PublishResponse:
    _teacher(session)
    raw_key = _valid_key(idempotency_key, "withdrawal idempotency")
    scope = f"WITHDRAW:{version_id}"
    key_hash = keyed_hash(resources.settings, "idempotency", raw_key)
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.session_id == session.id,
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key_hash == key_hash,
        )
    )
    if existing is not None and as_utc(existing.expires_at) > utc_now():
        return PublishResponse.model_validate_json(existing.response_body)
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    agent = db.get(Agent, version.agent_id)
    if agent is None or agent.published_version_id != version.id:
        raise ApiError(
            409,
            "VERSION_NOT_CURRENTLY_PUBLISHED",
            "Only the public version can withdraw.",
        )
    approval = _approval_review(db, version.id)
    now = utc_now()
    agent.published_version_id = None
    agent.updated_at = now
    version.state = VersionState.WITHDRAWN.value
    version.withdrawn_at = now
    version.updated_at = now
    response = PublishResponse(
        slug=agent.slug,
        public_path=f"/p/{agent.slug}",
        version_number=version.version_number,
    )
    db.add_all(
        [
            TeacherReview(
                id=str(uuid4()),
                version_id=version.id,
                evaluation_run_id=approval.evaluation_run_id,
                session_id=session.id,
                decision="WITHDRAW",
                feedback=None,
                created_at=now,
            ),
            IdempotencyRecord(
                id=str(uuid4()),
                session_id=session.id,
                scope=scope,
                key_hash=key_hash,
                request_hash=canonical_hash({}),
                response_status=200,
                response_body=response.model_dump_json(),
                created_at=now,
                expires_at=now + timedelta(hours=resources.settings.idempotency_hours),
            ),
            AuditEvent(
                id=str(uuid4()),
                session_id=session.id,
                actor_type="DEMO_SESSION",
                action="VERSION_WITHDRAWN",
                target_type="AGENT_VERSION",
                target_id=version.id,
                result="SUCCESS",
                created_at=now,
            ),
        ]
    )
    db.commit()
    return response


def get_public_agent(db: Session, slug: str) -> tuple[Agent, AgentVersion, PublicAgentView]:
    agent = db.scalar(select(Agent).where(Agent.slug == slug, Agent.deleted_at.is_(None)))
    version = (
        db.get(AgentVersion, agent.published_version_id)
        if agent and agent.published_version_id
        else None
    )
    if agent is None or version is None or version.state != VersionState.PUBLISHED.value:
        raise ApiError(404, "PUBLIC_AGENT_UNAVAILABLE", "This published Agent is unavailable.")
    document = (
        db.get(KnowledgeDocument, version.active_document_id)
        if version.active_document_id
        else None
    )
    if document is None or document.status != DocumentStatus.READY.value:
        raise ApiError(404, "PUBLIC_AGENT_UNAVAILABLE", "This published Agent is unavailable.")
    return (
        agent,
        version,
        PublicAgentView(
            slug=agent.slug,
            project_name=version.project_name,
            problem_to_solve=version.problem_to_solve,
            intended_users=version.intended_users,
            audience_age=version.audience_age,  # pyright: ignore[reportArgumentType]
            success_goal=version.success_goal,
            welcome_message=version.welcome_message,
            version_number=version.version_number,
            status="PUBLISHED",
            knowledge_source=SOURCE_ATTRIBUTION,
        ),
    )


def reserve_public_limits(db: Session, resources: RuntimeResources, client_ip: str) -> None:
    now = utc_now()
    subject_hash = keyed_hash(resources.settings, "public-ip", client_ip)
    windows = (
        (PUBLIC_HOUR_SCOPE, timedelta(hours=1), resources.settings.public_hourly_limit),
        (PUBLIC_DAY_SCOPE, timedelta(days=1), resources.settings.public_daily_limit),
    )
    for scope, duration, limit in windows:
        bucket = db.scalar(
            select(RateLimitBucket).where(
                RateLimitBucket.subject_hash == subject_hash,
                RateLimitBucket.scope == scope,
                RateLimitBucket.window_end > now,
            )
        )
        if bucket is not None and bucket.count >= limit:
            db.rollback()
            retry_after = max(1, math.ceil((as_utc(bucket.window_end) - now).total_seconds()))
            raise ApiError(
                429,
                "PUBLIC_RATE_LIMITED",
                "This network has reached the public demo limit. Try again later.",
                retryable=True,
                retry_after_seconds=retry_after,
            )
        if bucket is None:
            db.add(
                RateLimitBucket(
                    id=str(uuid4()),
                    subject_hash=subject_hash,
                    scope=scope,
                    window_start=now,
                    window_end=now + duration,
                    count=1,
                )
            )
        else:
            bucket.count += 1
    db.commit()


def create_public_run(
    db: Session,
    resources: RuntimeResources,
    store: TransientStore,
    slug: str,
    payload: PublicRunCreate,
    client_ip: str,
    idempotency_key: str | None,
) -> PublicRunCreateResponse:
    _, version, _ = get_public_agent(db, slug)
    raw_key = _valid_key(idempotency_key, "public idempotency")
    key_hash = keyed_hash(resources.settings, "public-key", f"{client_ip}:{slug}:{raw_key}")
    request_hash = keyed_hash(resources.settings, "public-request", payload.message)
    replay = store.public_replay(key_hash, request_hash)
    if replay is not None:
        return replay
    reserve_public_limits(db, resources, client_ip)
    now = utc_now()
    expires_at = now + timedelta(minutes=10)
    run_id = str(uuid4())
    token = secrets.token_urlsafe(32)
    token_hash = keyed_hash(resources.settings, "public-run-token", token)
    pii_category = detect_pii(payload.message)
    run = ChatRun(
        id=run_id,
        version_id=version.id,
        conversation_id=None,
        surface="PUBLIC",
        audience_age_override=None,
        phase=(ChatPhase.COMPLETED.value if pii_category else ChatPhase.QUEUED.value),
        status=(ChatStatus.COMPLETED.value if pii_category else ChatStatus.RUNNING.value),
        result_type=(ChatResultType.BLOCKED.value if pii_category else None),
        input_message_id=None,
        output_message_id=None,
        input_fingerprint=keyed_hash(
            resources.settings,
            "blocked-input" if pii_category else "public-input",
            pii_category or payload.message,
        ),
        online_model=resources.chat_provider.online_model,
        moderation_model=resources.chat_provider.moderation_model,
        embedding_model=resources.embedding_provider.model,
        input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
        estimated_cost_usd=0,
        retrieval_ms=0,
        provider_ms=0,
        total_ms=0,
        error_code=None,
        safe_error_message=None,
        retry_count=0,
        created_at=now,
        finished_at=now if pii_category else None,
        expires_at=expires_at,
    )
    db.add(run)
    if pii_category:
        from app.db.models import SafetyEvent

        db.add(
            SafetyEvent(
                id=str(uuid4()),
                run_id=run.id,
                version_id=version.id,
                category=pii_category,
                action="BLOCKED_BEFORE_PROVIDER",
                detector="DETERMINISTIC_PII_V1",
                safe_summary="Personal contact information was blocked before provider access.",
                created_at=now,
            )
        )
    db.commit()
    result = (
        ChatResultView(type=ChatResultType.BLOCKED, answer=SAFE_PRIVACY_ANSWER, citations=[])
        if pii_category
        else None
    )
    store.add_run(
        run.id,
        PublicMemoryRun(
            token_hash=token_hash,
            expires_at=expires_at,
            prompt=None if pii_category else payload.message,
            result=result,
        ),
    )
    response = PublicRunCreateResponse(
        run_id=run.id,
        run_token=token,
        phase=ChatPhase.QUEUED,
    )
    store.save_public_key(key_hash, request_hash, response, expires_at)
    return response


def process_public_run(resources: RuntimeResources, store: TransientStore, run_id: str) -> None:
    prompt = store.claim_prompt(run_id)
    if prompt is None:
        return
    store.save_result(run_id, process_public_chat(resources, run_id, prompt))


def get_public_run(
    db: Session,
    resources: RuntimeResources,
    store: TransientStore,
    run_id: str,
    token: str | None,
) -> PublicRunView:
    if not token:
        raise ApiError(404, "RUN_EXPIRED", "This public result is no longer available.")
    memory = store.get_run(run_id, keyed_hash(resources.settings, "public-run-token", token))
    run = db.get(ChatRun, run_id)
    if run is None or run.surface != "PUBLIC" or as_utc(run.expires_at) <= utc_now():
        raise ApiError(404, "RUN_EXPIRED", "This public result is no longer available.")
    phase = ChatPhase(run.phase)
    status = ChatStatus(run.status)
    result = memory.result if status == ChatStatus.COMPLETED else None
    if status == ChatStatus.COMPLETED and result is None:
        phase = ChatPhase.OUTPUT_VALIDATION
        status = ChatStatus.RUNNING
    error_code = run.error_code
    if error_code == "GLOBAL_MODEL_LIMITED":
        error_code = "GLOBAL_DEMO_LIMIT_REACHED"
    safe_error = run.safe_error_message
    if error_code == "GLOBAL_DEMO_LIMIT_REACHED":
        safe_error = "The public demo has reached its daily model limit. Try again later."
    return PublicRunView(
        id=run.id,
        phase=phase,
        status=status,
        display_stage=PHASE_COPY[phase.value],
        result=result,
        safe_error=safe_error,
        retryable=bool(run.error_code),
    )


def verify_admin(resources: RuntimeResources, candidate: str | None) -> None:
    supplied = (candidate or "").encode()
    expected = resources.settings.admin_reset_token.get_secret_value().encode()
    if not hmac.compare_digest(expected, supplied):
        raise ApiError(403, "ADMIN_TOKEN_INVALID", "The admin operation was not authorized.")


def seed_fixed_sample(
    db: Session, resources: RuntimeResources, agent_id: str, admin_token: str | None
) -> FixedSampleResponse:
    verify_admin(resources, admin_token)
    agent = db.get(Agent, agent_id)
    if agent is None or agent.published_version_id is None:
        raise ApiError(
            409,
            "FIXED_SAMPLE_NOT_PUBLISHED",
            "Publish the sample before protecting it.",
        )
    agent.is_fixed_sample = 1
    agent.updated_at = utc_now()
    db.add(
        AuditEvent(
            id=str(uuid4()),
            session_id=None,
            actor_type="ADMIN",
            action="FIXED_SAMPLE_SEEDED",
            target_type="AGENT",
            target_id=agent.id,
            result="SUCCESS",
            created_at=utc_now(),
        )
    )
    db.commit()
    return FixedSampleResponse(agent_id=agent.id, slug=agent.slug)


def reset_workspace(
    db: Session,
    resources: RuntimeResources,
    store: TransientStore,
    admin_token: str | None,
    idempotency_key: str | None,
) -> ResetResponse:
    verify_admin(resources, admin_token)
    raw_key = _valid_key(idempotency_key, "reset idempotency")
    key_hash = keyed_hash(resources.settings, "admin-reset", raw_key)
    replay = store.reset_replay(key_hash)
    if replay is not None:
        return replay
    targets = list(db.scalars(select(Agent).where(Agent.is_fixed_sample == 0)))
    preserved = int(
        db.scalar(select(func.count()).select_from(Agent).where(Agent.is_fixed_sample == 1)) or 0
    )
    target_ids = [agent.id for agent in targets]
    upload_root = resources.settings.uploads_path.resolve()
    paths: set[Path] = set()
    if target_ids:
        version_ids = list(
            db.scalars(select(AgentVersion.id).where(AgentVersion.agent_id.in_(target_ids)))
        )
        documents = (
            list(
                db.scalars(
                    select(KnowledgeDocument).where(KnowledgeDocument.version_id.in_(version_ids))
                )
            )
            if version_ids
            else []
        )
        for document in documents:
            path = Path(document.storage_path).resolve()
            try:
                path.relative_to(upload_root)
            except ValueError as error:
                raise ApiError(
                    500,
                    "RESET_PATH_INVALID",
                    "Reset found an unsafe upload path.",
                ) from error
            paths.add(path.parent)
        collection = resources.chroma.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
        for agent_id in target_ids:
            collection.delete(where={"agent_id": agent_id})
        for directory in paths:
            if directory.is_symlink():
                raise ApiError(500, "RESET_PATH_INVALID", "Reset found an unsafe upload path.")
            if directory.exists():
                shutil.rmtree(directory)
        for agent in targets:
            db.delete(agent)
    audit_id = str(uuid4())
    db.add(
        AuditEvent(
            id=audit_id,
            session_id=None,
            actor_type="ADMIN",
            action="DEMO_WORKSPACE_RESET",
            target_type=None,
            target_id=None,
            result="SUCCESS",
            created_at=utc_now(),
        )
    )
    db.commit()
    store.clear_runs()
    response = ResetResponse(
        reset_audit_id=audit_id,
        deleted_agents=len(targets),
        preserved_fixed_samples=preserved,
    )
    store.save_reset(key_hash, response)
    return response
