from __future__ import annotations

import re
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.api.schemas import (
    AgentAggregate,
    AgentCreate,
    AgentCreateResponse,
    AgentListResponse,
    AgentSummary,
    AgentVersionPatch,
    TeacherReviewView,
    VersionDetail,
    VersionSummary,
)
from app.core.config import Settings
from app.core.security import as_utc, canonical_hash, keyed_hash, utc_now
from app.db.models import (
    Agent,
    AgentVersion,
    AuditEvent,
    ChatRun,
    DemoSession,
    IdempotencyRecord,
    IngestionJob,
    KnowledgeDocument,
    TeacherReview,
)
from app.domain.enums import (
    AudienceAge,
    ChatStatus,
    DocumentStatus,
    IngestionState,
    ResponseLength,
    Role,
    Tone,
    VersionState,
)
from app.services.knowledge import get_knowledge_view

CREATE_SCOPE = "CREATE_AGENT"
SUBMIT_SCOPE = "SUBMIT_VERSION"


def _allowed_actions(role: str, state: str) -> list[str]:
    if role == Role.STUDENT.value and state == VersionState.DRAFT.value:
        return ["EDIT_DRAFT", "SUBMIT_VERSION"]
    if role == Role.TEACHER.value and state == VersionState.IN_REVIEW.value:
        return ["RUN_EVALUATION", "REQUEST_CHANGES", "APPROVE"]
    if role == Role.STUDENT.value and state in {
        VersionState.CHANGES_REQUESTED.value,
        VersionState.APPROVED.value,
        VersionState.PUBLISHED.value,
    }:
        return ["CREATE_NEXT_VERSION"]
    return []


def _next_action(role: str, state: str) -> str:
    if role == Role.STUDENT.value and state == VersionState.DRAFT.value:
        return "Continue defining the agent"
    if role == Role.TEACHER.value and state == VersionState.DRAFT.value:
        return "Waiting for student submission"
    if role == Role.TEACHER.value and state == VersionState.IN_REVIEW.value:
        return "Run the fixed evaluation suite"
    if state == VersionState.IN_REVIEW.value:
        return "Waiting for teacher evaluation"
    if role == Role.STUDENT.value and state == VersionState.CHANGES_REQUESTED.value:
        return "Review feedback and create the next version"
    if state == VersionState.APPROVED.value:
        return "Approved for publication"
    return "No action available"


def _version_summary(db: Session, version: AgentVersion) -> VersionSummary:
    knowledge_status, _ = get_knowledge_view(db, version)
    return VersionSummary(
        id=version.id,
        number=version.version_number,
        state=VersionState(version.state),
        knowledge_status=knowledge_status,
    )


def _version_detail(db: Session, version: AgentVersion, role: str) -> VersionDetail:
    knowledge_status, knowledge = get_knowledge_view(db, version)
    reviews = list(
        db.scalars(
            select(TeacherReview)
            .where(TeacherReview.version_id == version.id)
            .order_by(TeacherReview.created_at)
        )
    )
    return VersionDetail(
        id=version.id,
        agent_id=version.agent_id,
        version_number=version.version_number,
        state=VersionState(version.state),
        project_name=version.project_name,
        problem_to_solve=version.problem_to_solve,
        intended_users=version.intended_users,
        audience_age=AudienceAge(version.audience_age),
        success_goal=version.success_goal,
        welcome_message=version.welcome_message,
        tone=Tone(version.tone),
        response_length=ResponseLength(version.response_length),
        custom_instructions=version.custom_instructions,
        active_document_id=version.active_document_id,
        knowledge_status=knowledge_status,
        knowledge=knowledge,
        what_changed=version.what_changed,
        why_changed=version.why_changed,
        source_version_id=version.source_version_id,
        submitted_at=as_utc(version.submitted_at) if version.submitted_at else None,
        approved_at=as_utc(version.approved_at) if version.approved_at else None,
        reviews=[
            TeacherReviewView(
                id=review.id,
                evaluation_run_id=review.evaluation_run_id,
                decision=review.decision,  # pyright: ignore[reportArgumentType]
                feedback=review.feedback,
                created_at=as_utc(review.created_at),
            )
            for review in reviews
        ],
        allowed_actions=_allowed_actions(role, version.state),
        created_at=as_utc(version.created_at),
        updated_at=as_utc(version.updated_at),
    )


def _aggregate(
    db: Session, agent: Agent, role: str, versions: list[AgentVersion] | None = None
) -> AgentAggregate:
    visible_versions = versions or list(
        db.scalars(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent.id)
            .order_by(AgentVersion.version_number)
        )
    )
    current = next(
        (version for version in visible_versions if version.id == agent.current_draft_version_id),
        visible_versions[-1],
    )
    return AgentAggregate(
        id=agent.id,
        display_name=agent.display_name,
        slug=agent.slug,
        current_draft_version_id=agent.current_draft_version_id,
        published_version_id=agent.published_version_id,
        versions=[_version_summary(db, version) for version in visible_versions],
        allowed_actions=_allowed_actions(role, current.state),
    )


def _slug(project_name: str, agent_id: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-") or "agent"
    return f"{base[:80]}-{agent_id[:8]}"


def _require_student(session: DemoSession) -> None:
    if session.role != Role.STUDENT.value:
        raise ApiError(403, "STUDENT_ROLE_REQUIRED", "Switch to Student mode for this action.")


def list_agents(
    db: Session,
    session: DemoSession,
    state: VersionState | None = None,
    needs_review: bool | None = None,
) -> AgentListResponse:
    agents = list(
        db.scalars(
            select(Agent).where(Agent.deleted_at.is_(None)).order_by(Agent.updated_at.desc())
        )
    )
    summaries: list[AgentSummary] = []
    for agent in agents:
        version = (
            db.get(AgentVersion, agent.current_draft_version_id)
            if agent.current_draft_version_id
            else db.scalar(
                select(AgentVersion)
                .where(AgentVersion.agent_id == agent.id)
                .order_by(AgentVersion.version_number.desc())
                .limit(1)
            )
        )
        if version is None:
            continue
        if state is not None and version.state != state.value:
            continue
        is_review = version.state == VersionState.IN_REVIEW.value
        if needs_review is not None and is_review != needs_review:
            continue
        published_version = (
            db.get(AgentVersion, agent.published_version_id) if agent.published_version_id else None
        )
        summaries.append(
            AgentSummary(
                id=agent.id,
                display_name=agent.display_name,
                slug=agent.slug,
                current_version=_version_summary(db, version),
                published_version=(
                    _version_summary(db, published_version) if published_version else None
                ),
                allowed_actions=_allowed_actions(session.role, version.state),
                next_action=_next_action(session.role, version.state),
            )
        )
    return AgentListResponse(agents=summaries)


def get_agent(db: Session, session: DemoSession, agent_id: str) -> AgentAggregate:
    agent = db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        raise ApiError(404, "AGENT_NOT_FOUND", "The Agent was not found.")
    return _aggregate(db, agent, session.role)


def get_version(db: Session, session: DemoSession, version_id: str) -> VersionDetail:
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    agent = db.get(Agent, version.agent_id)
    if agent is None or agent.deleted_at is not None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    return _version_detail(db, version, session.role)


def create_agent(
    db: Session,
    settings: Settings,
    session: DemoSession,
    payload: AgentCreate,
    idempotency_key: str | None,
) -> AgentCreateResponse:
    _require_student(session)
    if not idempotency_key or not 8 <= len(idempotency_key) <= 200:
        raise ApiError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "A valid idempotency key is required for Agent creation.",
        )

    now = utc_now()
    key_hash = keyed_hash(settings, "idempotency", idempotency_key)
    request_hash = canonical_hash(payload.model_dump(mode="json"))
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.session_id == session.id,
            IdempotencyRecord.scope == CREATE_SCOPE,
            IdempotencyRecord.key_hash == key_hash,
        )
    )
    if existing is not None and as_utc(existing.expires_at) > now:
        if existing.request_hash != request_hash:
            raise ApiError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "This request key was already used for different Agent details.",
            )
        return AgentCreateResponse.model_validate_json(existing.response_body)
    if existing is not None:
        db.delete(existing)

    agent_id = str(uuid4())
    version_id = str(uuid4())
    agent = Agent(
        id=agent_id,
        slug=_slug(payload.project_name, agent_id),
        display_name=payload.project_name,
        current_draft_version_id=version_id,
        published_version_id=None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
        is_fixed_sample=0,
    )
    version = AgentVersion(
        id=version_id,
        agent_id=agent_id,
        version_number=1,
        state=VersionState.DRAFT.value,
        project_name=payload.project_name,
        problem_to_solve=payload.problem_to_solve,
        intended_users=payload.intended_users,
        audience_age=payload.audience_age.value,
        success_goal=payload.success_goal,
        welcome_message=payload.welcome_message,
        tone=payload.tone.value,
        response_length=payload.response_length.value,
        custom_instructions=payload.custom_instructions,
        what_changed=None,
        why_changed=None,
        source_version_id=None,
        active_document_id=None,
        submitted_at=None,
        approved_at=None,
        published_at=None,
        withdrawn_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add_all([agent, version])
    response = AgentCreateResponse(
        agent=_aggregate(db, agent, session.role, [version]),
        version=_version_detail(db, version, session.role),
    )
    db.add_all(
        [
            AuditEvent(
                id=str(uuid4()),
                session_id=session.id,
                actor_type="DEMO_SESSION",
                action="AGENT_CREATED",
                target_type="AGENT",
                target_id=agent_id,
                result="SUCCESS",
                created_at=now,
            ),
            IdempotencyRecord(
                id=str(uuid4()),
                session_id=session.id,
                scope=CREATE_SCOPE,
                key_hash=key_hash,
                request_hash=request_hash,
                response_status=201,
                response_body=response.model_dump_json(),
                created_at=now,
                expires_at=now + timedelta(hours=settings.idempotency_hours),
            ),
        ]
    )
    db.commit()
    return response


def update_version(
    db: Session,
    session: DemoSession,
    version_id: str,
    payload: AgentVersionPatch,
) -> VersionDetail:
    _require_student(session)
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    if version.state != VersionState.DRAFT.value:
        raise ApiError(409, "VERSION_IMMUTABLE", "Only a Draft version can be edited.")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(version, field, value.value if hasattr(value, "value") else value)
    version.updated_at = utc_now()
    agent = db.get(Agent, version.agent_id)
    if agent is None or agent.deleted_at is not None:
        raise ApiError(404, "AGENT_NOT_FOUND", "The Agent was not found.")
    if "project_name" in updates:
        agent.display_name = version.project_name
    agent.updated_at = version.updated_at
    db.add(
        AuditEvent(
            id=str(uuid4()),
            session_id=session.id,
            actor_type="DEMO_SESSION",
            action="DRAFT_UPDATED",
            target_type="AGENT_VERSION",
            target_id=version.id,
            result="SUCCESS",
            created_at=version.updated_at,
        )
    )
    db.commit()
    return _version_detail(db, version, session.role)


def submit_version(
    db: Session,
    settings: Settings,
    session: DemoSession,
    version_id: str,
    idempotency_key: str | None,
) -> VersionDetail:
    _require_student(session)
    if not idempotency_key or not 8 <= len(idempotency_key) <= 200:
        raise ApiError(400, "IDEMPOTENCY_KEY_REQUIRED", "A valid submission key is required.")
    key_hash = keyed_hash(settings, "idempotency", idempotency_key)
    request_hash = canonical_hash({"version_id": version_id})
    replay = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.session_id == session.id,
            IdempotencyRecord.scope == SUBMIT_SCOPE,
            IdempotencyRecord.key_hash == key_hash,
        )
    )
    if replay is not None and as_utc(replay.expires_at) > utc_now():
        if replay.request_hash != request_hash:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This submission key was already used.")
        return VersionDetail.model_validate_json(replay.response_body)
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    if version.state != VersionState.DRAFT.value:
        raise ApiError(409, "VERSION_IMMUTABLE", "This version is already submitted.")
    document = (
        db.get(KnowledgeDocument, version.active_document_id)
        if version.active_document_id
        else None
    )
    if document is None or document.status != DocumentStatus.READY.value:
        raise ApiError(409, "KNOWLEDGE_NOT_READY", "Add a Ready source before submission.")
    active_ingestion = db.scalar(
        select(IngestionJob).where(
            IngestionJob.state.in_(
                [
                    IngestionState.UPLOADED.value,
                    IngestionState.EXTRACTING.value,
                    IngestionState.CHUNKING.value,
                    IngestionState.EMBEDDING.value,
                ]
            )
        )
    )
    active_chat = db.scalar(
        select(ChatRun).where(
            ChatRun.version_id == version_id, ChatRun.status == ChatStatus.RUNNING.value
        )
    )
    if active_ingestion is not None or active_chat is not None:
        raise ApiError(409, "VERSION_BUSY", "Wait for active work before submission.")
    now = utc_now()
    version.state = VersionState.IN_REVIEW.value
    version.submitted_at = now
    version.updated_at = now
    agent = db.get(Agent, version.agent_id)
    if agent is None:
        raise ApiError(404, "AGENT_NOT_FOUND", "The Agent was not found.")
    agent.current_draft_version_id = None
    agent.updated_at = now
    response = _version_detail(db, version, session.role)
    db.add(
        IdempotencyRecord(
            id=str(uuid4()),
            session_id=session.id,
            scope=SUBMIT_SCOPE,
            key_hash=key_hash,
            request_hash=request_hash,
            response_status=200,
            response_body=response.model_dump_json(),
            created_at=now,
            expires_at=now + timedelta(hours=settings.idempotency_hours),
        )
    )
    db.add(
        AuditEvent(
            id=str(uuid4()),
            session_id=session.id,
            actor_type="DEMO_SESSION",
            action="VERSION_SUBMITTED",
            target_type="AGENT_VERSION",
            target_id=version.id,
            result="SUCCESS",
            created_at=now,
        )
    )
    db.commit()
    return response
