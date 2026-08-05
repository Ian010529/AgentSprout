from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, status

from app.api.dependencies import CurrentSession, DatabaseSession, MutationSession, RuntimeSettings
from app.api.schemas import (
    AgentAggregate,
    AgentCreate,
    AgentCreateResponse,
    AgentListResponse,
    AgentVersionPatch,
    VersionDetail,
)
from app.domain.enums import VersionState
from app.services.agents import create_agent, get_agent, get_version, list_agents, update_version

router = APIRouter(prefix="/studio", tags=["studio-agents"])


@router.get("/agents", response_model=AgentListResponse)
def read_agents(
    db: DatabaseSession,
    session: CurrentSession,
    state: VersionState | None = None,
    needs_review: bool | None = None,
) -> AgentListResponse:
    return list_agents(db, session, state, needs_review)


@router.post("/agents", response_model=AgentCreateResponse, status_code=status.HTTP_201_CREATED)
def add_agent(
    payload: AgentCreate,
    db: DatabaseSession,
    runtime_settings: RuntimeSettings,
    session: MutationSession,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AgentCreateResponse:
    return create_agent(db, runtime_settings, session, payload, idempotency_key)


@router.get("/agents/{agent_id}", response_model=AgentAggregate)
def read_agent(
    agent_id: str,
    db: DatabaseSession,
    session: CurrentSession,
) -> AgentAggregate:
    return get_agent(db, session, agent_id)


@router.get("/versions/{version_id}", response_model=VersionDetail)
def read_version(
    version_id: str,
    db: DatabaseSession,
    session: CurrentSession,
) -> VersionDetail:
    return get_version(db, session, version_id)


@router.patch("/versions/{version_id}", response_model=VersionDetail)
def edit_version(
    version_id: str,
    payload: AgentVersionPatch,
    db: DatabaseSession,
    session: MutationSession,
) -> VersionDetail:
    return update_version(db, session, version_id, payload)
