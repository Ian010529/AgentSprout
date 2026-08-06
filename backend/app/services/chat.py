# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
from __future__ import annotations

import json
import logging
import math
import re
import time
from datetime import timedelta
from typing import Any, TypedDict, cast
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.api.schemas import (
    ChatResultView,
    ChatRunCreate,
    ChatRunCreateResponse,
    ChatRunView,
    ChatTraceView,
    CitationView,
    ConversationMessageView,
    ConversationView,
    TraceNodeView,
)
from app.core.config import Settings
from app.core.security import as_utc, keyed_hash, utc_now
from app.db.models import (
    AgentVersion,
    ChatRun,
    DemoSession,
    IdempotencyRecord,
    KnowledgeDocument,
    Message,
    MessageCitation,
    RateLimitBucket,
    RunNodeTrace,
    SafetyEvent,
    StudioConversation,
)
from app.db.readiness import RuntimeResources
from app.domain.enums import (
    ChatIntent,
    ChatPhase,
    ChatResultType,
    ChatStatus,
    DocumentStatus,
    Role,
)
from app.providers.contracts import (
    ProviderCallRecord,
    ProviderOutputError,
    RuntimeProviderError,
)
from app.services.knowledge import RetrievedChunk, retrieve

logger = logging.getLogger(__name__)

CHAT_SCOPE = "CHAT_RUN"
STUDIO_CHAT_SCOPE = "STUDIO_CHAT_HOUR"
GLOBAL_MODEL_SCOPE = "GLOBAL_MODEL_DAY"
RETRYABLE_CHAT_ERRORS = {
    "PROVIDER_TIMEOUT",
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_UNAVAILABLE",
    "SERVICE_RESTARTED",
}
EMAIL_RE = re.compile(r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\s().-]*){7,15}(?!\d)")
ADDRESS_RE = re.compile(
    r"(?i)\b\d{1,6}\s+[a-z0-9][a-z0-9 .'-]{1,60}\s+"
    r"(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|court|ct|boulevard|blvd)\b"
)
PII_REQUEST_RE = re.compile(
    r"(?i)\b(?:tell|show|give|share|collect|find|reveal|what(?:'s| is))\b.{0,40}"
    r"\b(?:email|e-mail|phone|telephone|home address|street address)\b"
)

SAFE_PRIVACY_ANSWER = (
    "Keep personal contact details private. I can't use or repeat an email, phone number, "
    "or home address. Ask a trusted adult if you need help sharing information safely."
)
SAFE_MODERATION_ANSWER = (
    "I can't help with that request. We can switch to a safe ocean-learning question instead. "
    "If someone may be in immediate danger, tell a trusted adult or contact local emergency help."
)
SAFE_INJECTION_ANSWER = (
    "I can't reveal hidden instructions or ignore the safety and knowledge rules. "
    "I can still help with a question supported by the Ocean Literacy source."
)
SAFE_OUT_OF_KNOWLEDGE_ANSWER = (
    "I couldn't find enough support for that in the uploaded Ocean Literacy source. "
    "Try asking about ocean systems, climate, life, exploration, or people's connection "
    "to the ocean."
)


class GraphState(TypedDict):
    run_id: str
    message: str
    audience_age: str
    tone: str
    response_length: str
    custom_instructions: str
    intent: str
    retrieved: list[RetrievedChunk]
    calls: list[ProviderCallRecord]
    generated_answer: str
    cited_chunk_ids: tuple[str, ...]
    result_type: str
    final_answer: str
    safety_category: str


def detect_pii(message: str) -> str | None:
    if EMAIL_RE.search(message):
        return "PII_EMAIL"
    if ADDRESS_RE.search(message):
        return "PII_ADDRESS"
    if PHONE_RE.search(message):
        return "PII_PHONE"
    if PII_REQUEST_RE.search(message):
        return "PII_REQUEST"
    return None


def _window_bucket(
    db: Session,
    *,
    subject_hash: str,
    scope: str,
    duration: timedelta,
    limit: int,
    message: str,
) -> None:
    now = utc_now()
    bucket = db.scalar(
        select(RateLimitBucket).where(
            RateLimitBucket.subject_hash == subject_hash,
            RateLimitBucket.scope == scope,
            RateLimitBucket.window_end > now,
        )
    )
    if bucket is not None and bucket.count >= limit:
        retry_after = max(1, math.ceil((as_utc(bucket.window_end) - now).total_seconds()))
        raise ApiError(
            429,
            "CHAT_RATE_LIMITED" if scope == STUDIO_CHAT_SCOPE else "GLOBAL_MODEL_LIMITED",
            message,
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


def reserve_global_model_call(resources: RuntimeResources) -> None:
    with resources.session_factory() as db:
        _window_bucket(
            db,
            subject_hash=keyed_hash(resources.settings, "global-model", "single-instance"),
            scope=GLOBAL_MODEL_SCOPE,
            duration=timedelta(days=1),
            limit=resources.settings.global_daily_model_limit,
            message="The demo's daily model-call limit has been reached.",
        )


def _require_ready_version(db: Session, version_id: str) -> AgentVersion:
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    document = (
        db.get(KnowledgeDocument, version.active_document_id)
        if version.active_document_id
        else None
    )
    if document is None or document.status != DocumentStatus.READY.value:
        raise ApiError(409, "KNOWLEDGE_NOT_READY", "Add a Ready knowledge source before testing.")
    return version


def _conversation(
    db: Session,
    settings: Settings,
    version_id: str,
    conversation_id: str | None,
) -> StudioConversation:
    now = utc_now()
    if conversation_id:
        existing = db.get(StudioConversation, conversation_id)
        if existing is None or existing.version_id != version_id:
            raise ApiError(404, "CONVERSATION_NOT_FOUND", "The conversation was not found.")
        if as_utc(existing.expires_at) <= now:
            raise ApiError(409, "CONVERSATION_EXPIRED", "Start a new conversation to continue.")
        existing.updated_at = now
        return existing
    conversation = StudioConversation(
        id=str(uuid4()),
        version_id=version_id,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(days=settings.studio_retention_days),
    )
    db.add(conversation)
    return conversation


def _store_idempotency(
    db: Session,
    settings: Settings,
    session: DemoSession,
    key_hash: str,
    request_hash: str,
    response: ChatRunCreateResponse,
) -> None:
    now = utc_now()
    db.add(
        IdempotencyRecord(
            id=str(uuid4()),
            session_id=session.id,
            scope=CHAT_SCOPE,
            key_hash=key_hash,
            request_hash=request_hash,
            response_status=202,
            response_body=response.model_dump_json(),
            created_at=now,
            expires_at=now + timedelta(hours=settings.idempotency_hours),
        )
    )


def _existing_idempotent(
    db: Session,
    session: DemoSession,
    key_hash: str,
    request_hash: str,
) -> ChatRunCreateResponse | None:
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.session_id == session.id,
            IdempotencyRecord.scope == CHAT_SCOPE,
            IdempotencyRecord.key_hash == key_hash,
        )
    )
    if existing is None:
        return None
    if as_utc(existing.expires_at) <= utc_now():
        db.delete(existing)
        db.flush()
        return None
    if existing.request_hash != request_hash:
        raise ApiError(
            409,
            "IDEMPOTENCY_CONFLICT",
            "This request key was already used for a different Playground message.",
        )
    return ChatRunCreateResponse.model_validate_json(existing.response_body)


def _add_trace(
    db: Session,
    run_id: str,
    node_name: str,
    status: str,
    started_at: Any,
    duration_ms: int,
    summary: dict[str, object],
) -> None:
    sequence = (
        int(
            db.scalar(
                select(func.count()).select_from(RunNodeTrace).where(RunNodeTrace.run_id == run_id)
            )
            or 0
        )
        + 1
    )
    db.add(
        RunNodeTrace(
            id=str(uuid4()),
            run_id=run_id,
            node_name=node_name,
            sequence=sequence,
            status=status,
            started_at=started_at,
            finished_at=utc_now(),
            duration_ms=duration_ms,
            safe_summary_json=json.dumps(summary, separators=(",", ":"), sort_keys=True),
        )
    )


def _add_safety_event(
    db: Session,
    run: ChatRun,
    category: str,
    action: str,
    detector: str,
    summary: str,
) -> None:
    db.add(
        SafetyEvent(
            id=str(uuid4()),
            run_id=run.id,
            version_id=run.version_id,
            category=category,
            action=action,
            detector=detector,
            safe_summary=summary,
            created_at=utc_now(),
        )
    )


def create_chat_run(
    db: Session,
    resources: RuntimeResources,
    session: DemoSession,
    version_id: str,
    payload: ChatRunCreate,
    idempotency_key: str | None,
) -> ChatRunCreateResponse:
    _require_ready_version(db, version_id)
    if not idempotency_key or not 8 <= len(idempotency_key) <= 200:
        raise ApiError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "A valid idempotency key is required for Playground messages.",
        )
    key_hash = keyed_hash(resources.settings, "idempotency", idempotency_key)
    request_hash = keyed_hash(
        resources.settings,
        "chat-request",
        json.dumps(payload.model_dump(mode="json"), separators=(",", ":"), sort_keys=True),
    )
    replay = _existing_idempotent(db, session, key_hash, request_hash)
    if replay is not None:
        return replay
    _window_bucket(
        db,
        subject_hash=keyed_hash(resources.settings, "studio-chat", session.id),
        scope=STUDIO_CHAT_SCOPE,
        duration=timedelta(hours=1),
        limit=resources.settings.studio_hourly_limit,
        message="The Studio message limit has been reached. Try again later.",
    )

    now = utc_now()
    conversation = _conversation(db, resources.settings, version_id, payload.conversation_id)
    db.flush()
    run = ChatRun(
        id=str(uuid4()),
        version_id=version_id,
        conversation_id=conversation.id,
        surface="STUDIO",
        audience_age_override=None,
        phase=ChatPhase.QUEUED.value,
        status=ChatStatus.RUNNING.value,
        result_type=None,
        input_message_id=None,
        output_message_id=None,
        input_fingerprint=keyed_hash(resources.settings, "chat-input", payload.message),
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
        finished_at=None,
        expires_at=now + timedelta(days=resources.settings.studio_retention_days),
    )
    db.add(run)
    db.flush()

    pii_category = detect_pii(payload.message)
    if pii_category is not None:
        run.input_fingerprint = keyed_hash(resources.settings, "blocked-input", pii_category)
        run.phase = ChatPhase.COMPLETED.value
        run.status = ChatStatus.COMPLETED.value
        run.result_type = ChatResultType.BLOCKED.value
        run.finished_at = now
        output = Message(
            id=str(uuid4()),
            conversation_id=conversation.id,
            run_id=run.id,
            role="ASSISTANT",
            content=SAFE_PRIVACY_ANSWER,
            created_at=now,
        )
        db.add(output)
        db.flush()
        run.output_message_id = output.id
        _add_safety_event(
            db,
            run,
            pii_category,
            "BLOCKED_BEFORE_PROVIDER",
            "DETERMINISTIC_PII_V1",
            "Personal contact information was blocked before provider access.",
        )
        _add_trace(
            db,
            run.id,
            "PRIVACY_CHECK",
            "BLOCKED",
            now,
            0,
            {"category": pii_category, "provider_called": False, "raw_input_stored": False},
        )
    else:
        input_message = Message(
            id=str(uuid4()),
            conversation_id=conversation.id,
            run_id=run.id,
            role="USER",
            content=payload.message,
            created_at=now,
        )
        db.add(input_message)
        db.flush()
        run.input_message_id = input_message.id
        _add_trace(
            db,
            run.id,
            "PRIVACY_CHECK",
            "PASSED",
            now,
            0,
            {"category": None, "provider_called": False},
        )

    response = ChatRunCreateResponse(
        run_id=run.id,
        conversation_id=conversation.id,
        phase=ChatPhase.QUEUED,
    )
    _store_idempotency(db, resources.settings, session, key_hash, request_hash, response)
    db.commit()
    return response


def _begin_node(resources: RuntimeResources, run_id: str, phase: ChatPhase) -> Any:
    started_at = utc_now()
    with resources.session_factory() as db:
        run = db.get(ChatRun, run_id)
        if run is None:
            raise RuntimeError("chat run missing")
        run.phase = phase.value
        db.commit()
    return started_at


def _finish_node(
    resources: RuntimeResources,
    run_id: str,
    node_name: str,
    started_at: Any,
    started_clock: float,
    summary: dict[str, object],
) -> None:
    with resources.session_factory() as db:
        run = db.get(ChatRun, run_id)
        if run is not None and run.surface == "PUBLIC":
            return
        _add_trace(
            db,
            run_id,
            node_name,
            "COMPLETED",
            started_at,
            round((time.perf_counter() - started_clock) * 1000),
            summary,
        )
        db.commit()


def _record_safety(
    resources: RuntimeResources,
    run_id: str,
    category: str,
    action: str,
    detector: str,
    summary: str,
) -> None:
    with resources.session_factory() as db:
        run = db.get(ChatRun, run_id)
        if run is None:
            raise RuntimeError("chat run missing")
        _add_safety_event(db, run, category, action, detector, summary)
        db.commit()


def _build_graph(resources: RuntimeResources) -> Any:
    def moderate_input(state: GraphState) -> dict[str, Any]:
        started_at = _begin_node(resources, state["run_id"], ChatPhase.MODERATION)
        started_clock = time.perf_counter()
        outcome = resources.chat_provider.moderate(state["message"], "INPUT_MODERATION")
        result: dict[str, Any] = {"calls": [*state["calls"], outcome.call]}
        if outcome.flagged:
            category = outcome.categories[0] if outcome.categories else "UNSAFE_CONTENT"
            result.update(
                result_type=ChatResultType.BLOCKED.value,
                final_answer=SAFE_MODERATION_ANSWER,
                safety_category=category,
            )
            _record_safety(
                resources,
                state["run_id"],
                category,
                "BLOCKED_BY_INPUT_MODERATION",
                resources.chat_provider.moderation_model,
                "Input moderation blocked unsafe content.",
            )
        _finish_node(
            resources,
            state["run_id"],
            "INPUT_MODERATION",
            started_at,
            started_clock,
            {"flagged": outcome.flagged, "categories": list(outcome.categories)},
        )
        return result

    def classify_intent(state: GraphState) -> dict[str, Any]:
        started_at = _begin_node(resources, state["run_id"], ChatPhase.INTENT_CLASSIFICATION)
        started_clock = time.perf_counter()
        reserve_global_model_call(resources)
        outcome = resources.chat_provider.classify(state["message"])
        _finish_node(
            resources,
            state["run_id"],
            "INTENT_CLASSIFICATION",
            started_at,
            started_clock,
            {"intent": outcome.intent, "model": outcome.call.model},
        )
        return {
            "intent": outcome.intent,
            "calls": [*state["calls"], outcome.call],
        }

    def refuse_injection(state: GraphState) -> dict[str, Any]:
        started_at = _begin_node(resources, state["run_id"], ChatPhase.OUTPUT_VALIDATION)
        started_clock = time.perf_counter()
        _record_safety(
            resources,
            state["run_id"],
            "PROMPT_INJECTION",
            "REFUSED_AND_REDIRECTED",
            "STRUCTURED_INTENT_V1",
            "A request to override or reveal protected instructions was refused.",
        )
        _finish_node(
            resources,
            state["run_id"],
            "INJECTION_REFUSAL",
            started_at,
            started_clock,
            {"category": "PROMPT_INJECTION", "generation_called": False},
        )
        return {
            "result_type": ChatResultType.REFUSED.value,
            "final_answer": SAFE_INJECTION_ANSWER,
            "safety_category": "PROMPT_INJECTION",
        }

    def retrieve_evidence(state: GraphState) -> dict[str, Any]:
        started_at = _begin_node(resources, state["run_id"], ChatPhase.RETRIEVAL)
        started_clock = time.perf_counter()
        chunks = retrieve(resources, _run_version_id(resources, state["run_id"]), state["message"])
        elapsed = round((time.perf_counter() - started_clock) * 1000)
        with resources.session_factory() as db:
            run = db.get(ChatRun, state["run_id"])
            if run is not None:
                run.retrieval_ms = elapsed
                db.commit()
        summary_chunks = [
            {
                "chunk_id": chunk.id,
                "page": chunk.page_number,
                "rank": rank,
                "similarity": round(chunk.similarity, 4),
            }
            for rank, chunk in enumerate(chunks, 1)
        ]
        _finish_node(
            resources,
            state["run_id"],
            "RETRIEVAL",
            started_at,
            started_clock,
            {"result_count": len(chunks), "chunks": summary_chunks},
        )
        if not chunks:
            _record_safety(
                resources,
                state["run_id"],
                "KNOWLEDGE_BOUNDARY",
                "REFUSED_WITHOUT_GENERATION",
                "RAG_THRESHOLD",
                "No retrieved evidence met the configured similarity threshold.",
            )
            return {
                "retrieved": [],
                "result_type": ChatResultType.REFUSED.value,
                "final_answer": SAFE_OUT_OF_KNOWLEDGE_ANSWER,
                "safety_category": "KNOWLEDGE_BOUNDARY",
            }
        return {"retrieved": chunks}

    def generate_answer(state: GraphState) -> dict[str, Any]:
        started_at = _begin_node(resources, state["run_id"], ChatPhase.GENERATION)
        started_clock = time.perf_counter()
        reserve_global_model_call(resources)
        evidence: list[dict[str, object]] = [
            {
                "chunk_id": chunk.id,
                "filename": chunk.filename,
                "page_number": chunk.page_number,
                "excerpt": chunk.text,
            }
            for chunk in state["retrieved"]
        ]
        homework = state["intent"] == ChatIntent.HOMEWORK.value
        outcome = resources.chat_provider.generate(
            message=state["message"],
            evidence=evidence,
            audience_age=state["audience_age"],
            tone=state["tone"],
            response_length=state["response_length"],
            custom_instructions=state["custom_instructions"],
            homework=homework,
        )
        _finish_node(
            resources,
            state["run_id"],
            "GENERATION",
            started_at,
            started_clock,
            {
                "model": outcome.call.model,
                "input_tokens": outcome.call.input_tokens,
                "output_tokens": outcome.call.output_tokens,
                "citation_count": len(outcome.cited_chunk_ids),
                "homework_guidance": homework,
            },
        )
        if homework:
            _record_safety(
                resources,
                state["run_id"],
                "HOMEWORK",
                "GUIDED_NOT_COMPLETED",
                "STRUCTURED_INTENT_V1",
                "The response was constrained to explanation, hints, and a guiding question.",
            )
        return {
            "generated_answer": outcome.answer,
            "cited_chunk_ids": outcome.cited_chunk_ids,
            "calls": [*state["calls"], outcome.call],
            "result_type": (
                ChatResultType.GUIDED.value if homework else ChatResultType.ANSWERED.value
            ),
        }

    def moderate_output(state: GraphState) -> dict[str, Any]:
        started_at = _begin_node(resources, state["run_id"], ChatPhase.OUTPUT_VALIDATION)
        started_clock = time.perf_counter()
        outcome = resources.chat_provider.moderate(state["generated_answer"], "OUTPUT_MODERATION")
        result: dict[str, Any] = {"calls": [*state["calls"], outcome.call]}
        if outcome.flagged:
            category = outcome.categories[0] if outcome.categories else "UNSAFE_OUTPUT"
            result.update(
                generated_answer="",
                cited_chunk_ids=(),
                result_type=ChatResultType.BLOCKED.value,
                final_answer=SAFE_MODERATION_ANSWER,
                safety_category=category,
            )
            _record_safety(
                resources,
                state["run_id"],
                category,
                "UNSAFE_OUTPUT_DISCARDED",
                resources.chat_provider.moderation_model,
                "Generated output was discarded before persistence or display.",
            )
        _finish_node(
            resources,
            state["run_id"],
            "OUTPUT_MODERATION",
            started_at,
            started_clock,
            {"flagged": outcome.flagged, "categories": list(outcome.categories)},
        )
        return result

    def validate_output(state: GraphState) -> dict[str, Any]:
        started_at = _begin_node(resources, state["run_id"], ChatPhase.OUTPUT_VALIDATION)
        started_clock = time.perf_counter()
        allowed = {chunk.id for chunk in state["retrieved"]}
        cited = tuple(dict.fromkeys(state["cited_chunk_ids"]))
        valid = bool(state["generated_answer"].strip()) and bool(cited)
        valid = valid and all(chunk_id in allowed for chunk_id in cited)
        _finish_node(
            resources,
            state["run_id"],
            "CITATION_VALIDATION",
            started_at,
            started_clock,
            {"valid": valid, "citation_count": len(cited), "allowlist_count": len(allowed)},
        )
        if not valid:
            raise ProviderOutputError
        return {"final_answer": state["generated_answer"], "cited_chunk_ids": cited}

    def persist_result(state: GraphState) -> dict[str, Any]:
        started_at = _begin_node(resources, state["run_id"], ChatPhase.OUTPUT_VALIDATION)
        started_clock = time.perf_counter()
        _persist_final_result(resources, state)
        _finish_node(
            resources,
            state["run_id"],
            "PERSIST_VALIDATED_RESULT",
            started_at,
            started_clock,
            {"result_type": state["result_type"], "raw_model_output_stored": False},
        )
        return {}

    graph = StateGraph(GraphState)
    graph.add_node("input_moderation", moderate_input)
    graph.add_node("intent_classification", classify_intent)
    graph.add_node("injection_refusal", refuse_injection)
    graph.add_node("retrieval", retrieve_evidence)
    graph.add_node("generation", generate_answer)
    graph.add_node("output_moderation", moderate_output)
    graph.add_node("citation_validation", validate_output)
    graph.add_node("persist", persist_result)
    graph.add_edge(START, "input_moderation")

    def after_moderation(state: GraphState) -> str:
        return "blocked" if state["result_type"] else "continue"

    def after_classification(state: GraphState) -> str:
        return "injection" if state["intent"] == ChatIntent.INJECTION.value else "retrieve"

    def after_retrieval(state: GraphState) -> str:
        return "found" if state["retrieved"] else "missing"

    def after_output_moderation(state: GraphState) -> str:
        return "blocked" if state["final_answer"] else "validate"

    graph.add_conditional_edges(
        "input_moderation",
        after_moderation,
        {"blocked": "persist", "continue": "intent_classification"},
    )
    graph.add_conditional_edges(
        "intent_classification",
        after_classification,
        {"injection": "injection_refusal", "retrieve": "retrieval"},
    )
    graph.add_edge("injection_refusal", "persist")
    graph.add_conditional_edges(
        "retrieval",
        after_retrieval,
        {"found": "generation", "missing": "persist"},
    )
    graph.add_edge("generation", "output_moderation")
    graph.add_conditional_edges(
        "output_moderation",
        after_output_moderation,
        {"blocked": "persist", "validate": "citation_validation"},
    )
    graph.add_edge("citation_validation", "persist")
    graph.add_edge("persist", END)
    return graph.compile()


def _run_version_id(resources: RuntimeResources, run_id: str) -> str:
    with resources.session_factory() as db:
        run = db.get(ChatRun, run_id)
        if run is None:
            raise RuntimeError("chat run missing")
        return run.version_id


def _persist_final_result(resources: RuntimeResources, state: GraphState) -> None:
    now = utc_now()
    calls = state.get("calls", [])
    with resources.session_factory() as db:
        run = db.get(ChatRun, state["run_id"])
        if run is None:
            raise RuntimeError("chat run missing")
        if run.surface == "PUBLIC":
            run.phase = ChatPhase.COMPLETED.value
            run.status = ChatStatus.COMPLETED.value
            run.result_type = state["result_type"]
            run.input_tokens = sum(call.input_tokens for call in calls)
            run.output_tokens = sum(call.output_tokens for call in calls)
            run.reasoning_tokens = sum(call.reasoning_tokens for call in calls)
            run.provider_ms = sum(call.latency_ms for call in calls)
            run.estimated_cost_usd = round(
                run.input_tokens * 0.15 / 1_000_000 + run.output_tokens * 0.60 / 1_000_000,
                8,
            )
            run.total_ms = round((now - as_utc(run.created_at)).total_seconds() * 1000)
            run.finished_at = now
            db.commit()
            return
        if run.conversation_id is None:
            raise RuntimeError("chat conversation missing")
        output = Message(
            id=str(uuid4()),
            conversation_id=run.conversation_id,
            run_id=run.id,
            role="ASSISTANT",
            content=state["final_answer"],
            created_at=now,
        )
        db.add(output)
        db.flush()
        retrieved = {chunk.id: chunk for chunk in state.get("retrieved", [])}
        for rank, chunk_id in enumerate(state.get("cited_chunk_ids", ()), 1):
            chunk = retrieved[chunk_id]
            db.add(
                MessageCitation(
                    id=str(uuid4()),
                    message_id=output.id,
                    chunk_id=chunk.id,
                    filename=chunk.filename,
                    page_number=chunk.page_number,
                    excerpt=chunk.text[:500],
                    rank=rank,
                )
            )
        run.output_message_id = output.id
        run.phase = ChatPhase.COMPLETED.value
        run.status = ChatStatus.COMPLETED.value
        run.result_type = state["result_type"]
        run.input_tokens = sum(call.input_tokens for call in calls)
        run.output_tokens = sum(call.output_tokens for call in calls)
        run.reasoning_tokens = sum(call.reasoning_tokens for call in calls)
        run.provider_ms = sum(call.latency_ms for call in calls)
        run.estimated_cost_usd = round(
            run.input_tokens * 0.15 / 1_000_000 + run.output_tokens * 0.60 / 1_000_000,
            8,
        )
        run.total_ms = round((now - as_utc(run.created_at)).total_seconds() * 1000)
        run.finished_at = now
        conversation = db.get(StudioConversation, run.conversation_id)
        if conversation is not None:
            conversation.updated_at = now
        db.commit()


def _fail_run(resources: RuntimeResources, run_id: str, code: str, retryable: bool) -> None:
    safe_message = (
        "The model service is temporarily unavailable. Try this message again."
        if retryable
        else "The answer could not be safely validated. Try a clearer knowledge question."
    )
    now = utc_now()
    with resources.session_factory() as db:
        run = db.get(ChatRun, run_id)
        if run is None:
            return
        run.phase = ChatPhase.FAILED.value
        run.status = ChatStatus.FAILED.value
        run.result_type = ChatResultType.FAILED.value
        run.error_code = code
        run.safe_error_message = safe_message
        run.total_ms = round((now - as_utc(run.created_at)).total_seconds() * 1000)
        run.finished_at = now
        db.commit()


def process_chat_run(resources: RuntimeResources, run_id: str) -> None:
    try:
        with resources.session_factory() as db:
            run = db.get(ChatRun, run_id)
            if run is None or run.status != ChatStatus.RUNNING.value:
                return
            input_message = db.get(Message, run.input_message_id) if run.input_message_id else None
            version = db.get(AgentVersion, run.version_id)
            if input_message is None or version is None:
                raise RuntimeError("chat run source missing")
            state: GraphState = {
                "run_id": run.id,
                "message": input_message.content,
                "audience_age": run.audience_age_override or version.audience_age,
                "tone": version.tone,
                "response_length": version.response_length,
                "custom_instructions": version.custom_instructions,
                "intent": ChatIntent.KNOWLEDGE.value,
                "retrieved": [],
                "calls": [],
                "generated_answer": "",
                "cited_chunk_ids": (),
                "result_type": "",
                "final_answer": "",
                "safety_category": "",
            }
        graph = _build_graph(resources)
        graph.invoke(state)
    except RuntimeProviderError as error:
        _fail_run(resources, run_id, error.code, error.retryable)
    except ProviderOutputError:
        _fail_run(resources, run_id, "OUTPUT_VALIDATION_FAILED", False)
    except ApiError as error:
        _fail_run(resources, run_id, error.code, error.retryable)
    except Exception:
        logger.exception("Chat run failed", extra={"run_id": run_id})
        _fail_run(resources, run_id, "CHAT_RUNTIME_FAILED", False)


def process_public_chat(
    resources: RuntimeResources, run_id: str, message: str
) -> ChatResultView | None:
    try:
        with resources.session_factory() as db:
            run = db.get(ChatRun, run_id)
            if run is None or run.surface != "PUBLIC" or run.status != ChatStatus.RUNNING.value:
                return None
            version = db.get(AgentVersion, run.version_id)
            if version is None:
                raise RuntimeError("public version missing")
            state: GraphState = {
                "run_id": run.id,
                "message": message,
                "audience_age": version.audience_age,
                "tone": version.tone,
                "response_length": version.response_length,
                "custom_instructions": version.custom_instructions,
                "intent": ChatIntent.KNOWLEDGE.value,
                "retrieved": [],
                "calls": [],
                "generated_answer": "",
                "cited_chunk_ids": (),
                "result_type": "",
                "final_answer": "",
                "safety_category": "",
            }
        final = cast(GraphState, _build_graph(resources).invoke(state))
        retrieved = {chunk.id: chunk for chunk in final.get("retrieved", [])}
        citations = [
            CitationView(
                chunk_id=chunk_id,
                filename=retrieved[chunk_id].filename,
                page_number=retrieved[chunk_id].page_number,
                excerpt=retrieved[chunk_id].text[:500],
            )
            for chunk_id in final.get("cited_chunk_ids", ())
            if chunk_id in retrieved
        ]
        return ChatResultView(
            type=ChatResultType(final["result_type"]),
            answer=final["final_answer"],
            citations=citations,
        )
    except RuntimeProviderError as error:
        _fail_run(resources, run_id, error.code, error.retryable)
    except ProviderOutputError:
        _fail_run(resources, run_id, "OUTPUT_VALIDATION_FAILED", False)
    except ApiError as error:
        _fail_run(resources, run_id, error.code, error.retryable)
    except Exception:
        logger.exception("Public chat run failed", extra={"run_id": run_id})
        _fail_run(resources, run_id, "CHAT_RUNTIME_FAILED", False)
    return None


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
    _require_ready_version(db, version_id)
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
