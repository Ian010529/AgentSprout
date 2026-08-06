from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Header, Request

from app.api.dependencies import DatabaseSession, RuntimeResource
from app.api.schemas import FixedSampleResponse, ResetResponse
from app.services.public_store import TransientStore
from app.services.publication import reset_workspace, seed_fixed_sample

router = APIRouter(prefix="/admin", tags=["admin-maintenance"])


@router.post("/seed-fixed-sample/{agent_id}", response_model=FixedSampleResponse)
def protect_sample(
    agent_id: str,
    db: DatabaseSession,
    resources: RuntimeResource,
    admin_token: Annotated[str | None, Header(alias="X-Admin-Reset-Token")] = None,
) -> FixedSampleResponse:
    return seed_fixed_sample(db, resources, agent_id, admin_token)


@router.post("/reset-demo-workspace", response_model=ResetResponse)
def reset_demo(
    request: Request,
    db: DatabaseSession,
    resources: RuntimeResource,
    admin_token: Annotated[str | None, Header(alias="X-Admin-Reset-Token")] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ResetResponse:
    store = cast(TransientStore, request.app.state.transient_store)
    return reset_workspace(db, resources, store, admin_token, idempotency_key)
