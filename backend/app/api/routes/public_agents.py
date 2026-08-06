from __future__ import annotations

import asyncio
from typing import Annotated, cast

from fastapi import APIRouter, Header, Request, Response, status

from app.api.dependencies import DatabaseSession, RuntimeResource
from app.api.errors import ApiError
from app.api.schemas import (
    PublicAgentView,
    PublicRunCreate,
    PublicRunCreateResponse,
    PublicRunView,
)
from app.db.readiness import RuntimeResources
from app.services.public_store import TransientStore
from app.services.publication import (
    create_public_run,
    get_public_agent,
    get_public_run,
    process_public_run,
)

router = APIRouter(prefix="/public", tags=["published-agent"])


def _store(request: Request) -> TransientStore:
    return cast(TransientStore, request.app.state.transient_store)


def _client_ip(request: Request) -> str:
    # Uvicorn may replace request.client only when its trusted-proxy configuration accepts
    # forwarded headers. Application code never trusts a browser-supplied header directly.
    return request.client.host if request.client else "unknown"


def _allow_public_origin(request: Request) -> None:
    origin = request.headers.get("Origin")
    allowed = request.app.state.resources.settings.allowed_origins
    if origin is not None and origin not in allowed:
        raise ApiError(403, "ORIGIN_DENIED", "This request origin is not allowed.")


def _schedule(
    request: Request, resources: RuntimeResources, store: TransientStore, run_id: str
) -> None:
    run_ids = cast(set[str], request.app.state.public_run_ids)
    if run_id in run_ids:
        return
    run_ids.add(run_id)
    task = asyncio.create_task(asyncio.to_thread(process_public_run, resources, store, run_id))
    tasks = cast(set[asyncio.Task[None]], request.app.state.public_tasks)
    tasks.add(task)

    def complete(completed: asyncio.Task[None]) -> None:
        tasks.discard(completed)
        run_ids.discard(run_id)

    task.add_done_callback(complete)


@router.get("/agents/{slug}", response_model=PublicAgentView)
def read_public_agent(slug: str, response: Response, db: DatabaseSession) -> PublicAgentView:
    response.headers["Cache-Control"] = "public, max-age=60"
    return get_public_agent(db, slug)[2]


@router.post(
    "/agents/{slug}/runs",
    response_model=PublicRunCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_public_run(
    request: Request,
    http_response: Response,
    slug: str,
    payload: PublicRunCreate,
    db: DatabaseSession,
    resources: RuntimeResource,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PublicRunCreateResponse:
    http_response.headers["Cache-Control"] = "no-store"
    _allow_public_origin(request)
    store = _store(request)
    response = create_public_run(
        db, resources, store, slug, payload, _client_ip(request), idempotency_key
    )
    _schedule(request, resources, store, response.run_id)
    return response


@router.get("/runs/{run_id}", response_model=PublicRunView)
def read_public_run(
    request: Request,
    response: Response,
    run_id: str,
    db: DatabaseSession,
    resources: RuntimeResource,
    run_token: Annotated[str | None, Header(alias="X-Public-Run-Token")] = None,
) -> PublicRunView:
    response.headers["Cache-Control"] = "no-store"
    return get_public_run(db, resources, _store(request), run_id, run_token)
