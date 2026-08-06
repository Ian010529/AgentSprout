"""Read-only Chat projections and user-facing run phase presentation."""

from __future__ import annotations

import json
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import as_utc, utc_now
from app.db.models import (
    ChatRun,
    DemoSession,
    Message,
    MessageCitation,
    RunNodeTrace,
    StudioConversation,
)
from app.domain.contracts import (
    ChatResultView,
    ChatRunView,
    ChatTraceView,
    CitationView,
    ConversationMessageView,
    ConversationView,
    TraceNodeView,
)
from app.domain.enums import ChatPhase, ChatResultType, ChatStatus, Role
from app.domain.errors import ApiError
from app.services.chat_access import require_ready_version

RETRYABLE_CHAT_ERRORS = {
    "PROVIDER_TIMEOUT",
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_UNAVAILABLE",
    "SERVICE_RESTARTED",
}

PHASE_COPY = {
    ChatPhase.QUEUED.value: "Queued for safe processing…",
    ChatPhase.PRIVACY_CHECK.value: "Checking privacy…",
    ChatPhase.MODERATION.value: "Checking safety…",
    ChatPhase.INTENT_CLASSIFICATION.value: "Understanding the learning request…",
    ChatPhase.RETRIEVAL.value: "Searching the knowledge base…",
    ChatPhase.GENERATION.value: "Preparing an age-appropriate answer…",
    ChatPhase.OUTPUT_VALIDATION.value: "Verifying safety and citations…",
    ChatPhase.COMPLETED.value: "Answer ready",
    ChatPhase.FAILED.value: "Run needs attention",
}


def _citations(db: Session, message_id: str | None) -> list[CitationView]:
    if message_id is None:
        return []
    rows = list(
        db.scalars(
            select(MessageCitation)
            .where(MessageCitation.message_id == message_id)
            .order_by(MessageCitation.rank)
        )
    )
    return [
        CitationView(
            chunk_id=row.chunk_id,
            filename=row.filename,
            page_number=row.page_number,
            excerpt=row.excerpt,
        )
        for row in rows
    ]


def get_chat_run(db: Session, run_id: str) -> ChatRunView:
    run = db.get(ChatRun, run_id)
    if run is None or run.surface != "STUDIO" or run.conversation_id is None:
        raise ApiError(404, "CHAT_RUN_NOT_FOUND", "The Playground run was not found.")
    result = None
    if run.status == ChatStatus.COMPLETED.value and run.output_message_id:
        output = db.get(Message, run.output_message_id)
        if output is not None and run.result_type is not None:
            result = ChatResultView(
                type=ChatResultType(run.result_type),
                answer=output.content,
                citations=_citations(db, output.id),
            )
    return ChatRunView(
        id=run.id,
        conversation_id=run.conversation_id,
        phase=ChatPhase(run.phase),
        status=ChatStatus(run.status),
        display_stage=PHASE_COPY[run.phase],
        result=result,
        safe_error=run.safe_error_message,
        retryable=run.error_code in RETRYABLE_CHAT_ERRORS,
    )


def get_conversation(db: Session, conversation_id: str) -> ConversationView:
    conversation = db.get(StudioConversation, conversation_id)
    if conversation is None:
        raise ApiError(404, "CONVERSATION_NOT_FOUND", "The conversation was not found.")
    messages = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at, Message.id)
        )
    )
    return ConversationView(
        id=conversation.id,
        version_id=conversation.version_id,
        messages=[
            ConversationMessageView(
                id=message.id,
                run_id=message.run_id,
                role=cast(Any, message.role),
                content=message.content,
                result_type=(
                    ChatResultType(run.result_type)
                    if (run := db.get(ChatRun, message.run_id)) is not None
                    and run.result_type is not None
                    and message.role == "ASSISTANT"
                    else None
                ),
                citations=_citations(db, message.id),
                created_at=as_utc(message.created_at),
            )
            for message in messages
        ],
        updated_at=as_utc(conversation.updated_at),
    )


def get_latest_conversation(db: Session, version_id: str) -> ConversationView | None:
    require_ready_version(db, version_id)
    conversation = db.scalar(
        select(StudioConversation)
        .where(
            StudioConversation.version_id == version_id,
            StudioConversation.expires_at > utc_now(),
        )
        .order_by(StudioConversation.updated_at.desc())
    )
    return get_conversation(db, conversation.id) if conversation is not None else None


def get_trace(db: Session, session: DemoSession, run_id: str) -> ChatTraceView:
    if session.role != Role.TEACHER.value:
        raise ApiError(403, "TEACHER_ROLE_REQUIRED", "Switch to Teacher mode to inspect traces.")
    run = db.get(ChatRun, run_id)
    if run is None or run.surface != "STUDIO":
        raise ApiError(404, "CHAT_RUN_NOT_FOUND", "The Playground run was not found.")
    traces = list(
        db.scalars(
            select(RunNodeTrace)
            .where(RunNodeTrace.run_id == run.id)
            .order_by(RunNodeTrace.sequence)
        )
    )
    return ChatTraceView(
        run_id=run.id,
        result_type=ChatResultType(run.result_type) if run.result_type else None,
        nodes=[
            TraceNodeView(
                node_name=trace.node_name,
                sequence=trace.sequence,
                status=trace.status,
                duration_ms=trace.duration_ms,
                safe_summary=cast(dict[str, object], json.loads(trace.safe_summary_json)),
            )
            for trace in traces
        ],
        models={
            "online": run.online_model,
            "moderation": run.moderation_model,
            "embedding": run.embedding_model,
        },
        usage={
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "reasoning_tokens": run.reasoning_tokens,
            "estimated_cost_usd": float(run.estimated_cost_usd),
            "retrieval_ms": run.retrieval_ms,
            "provider_ms": run.provider_ms,
            "total_ms": run.total_ms,
            "retry_count": run.retry_count,
        },
        error_code=run.error_code,
    )
