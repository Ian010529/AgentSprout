from __future__ import annotations

import asyncio
from typing import Annotated, cast

from fastapi import APIRouter, Header, Request, status

from app.api.dependencies import CurrentSession, DatabaseSession, MutationSession, RuntimeResource
from app.api.schemas import (
    ChatRunCreate,
    ChatRunCreateResponse,
    ChatRunView,
    ChatTraceView,
    ConversationView,
)
from app.db.readiness import RuntimeResources
from app.domain.enums import ChatStatus
from app.services.chat import create_chat_run, process_chat_run
from app.services.chat_queries import (
    get_chat_run,
    get_conversation,
    get_latest_conversation,
    get_trace,
)

router = APIRouter(prefix="/studio", tags=["studio-playground"])


def _schedule(request: Request, resources: RuntimeResources, run_id: str) -> None:
    run_ids = cast(set[str], request.app.state.chat_run_ids)
    if run_id in run_ids:
        return
    run_ids.add(run_id)
    task = asyncio.create_task(asyncio.to_thread(process_chat_run, resources, run_id))
    tasks = cast(set[asyncio.Task[None]], request.app.state.chat_tasks)
    tasks.add(task)

    def complete(completed: asyncio.Task[None]) -> None:
        tasks.discard(completed)
        run_ids.discard(run_id)

    task.add_done_callback(complete)


@router.post(
    "/versions/{version_id}/runs",
    response_model=ChatRunCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_chat_run(
    request: Request,
    version_id: str,
    payload: ChatRunCreate,
    db: DatabaseSession,
    resources: RuntimeResource,
    session: MutationSession,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ChatRunCreateResponse:
    response = create_chat_run(db, resources, session, version_id, payload, idempotency_key)
    if get_chat_run(db, response.run_id).status == ChatStatus.RUNNING:
        _schedule(request, resources, response.run_id)
    return response


@router.get("/runs/{run_id}", response_model=ChatRunView)
def read_chat_run(
    run_id: str,
    db: DatabaseSession,
    _session: CurrentSession,
) -> ChatRunView:
    return get_chat_run(db, run_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationView)
def read_conversation(
    conversation_id: str,
    db: DatabaseSession,
    _session: CurrentSession,
) -> ConversationView:
    return get_conversation(db, conversation_id)


@router.get(
    "/versions/{version_id}/conversation",
    response_model=ConversationView | None,
)
def read_latest_conversation(
    version_id: str,
    db: DatabaseSession,
    _session: CurrentSession,
) -> ConversationView | None:
    return get_latest_conversation(db, version_id)


@router.get("/runs/{run_id}/trace", response_model=ChatTraceView)
def read_chat_trace(
    run_id: str,
    db: DatabaseSession,
    session: CurrentSession,
) -> ChatTraceView:
    return get_trace(db, session, run_id)
