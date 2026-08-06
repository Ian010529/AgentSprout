from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.core.config import Settings
from app.db.models import DemoSession
from app.db.readiness import RuntimeResources
from app.services.sessions import SESSION_COOKIE, active_session, validate_csrf


def resources(request: Request) -> RuntimeResources:
    return request.app.state.resources


def settings(request: Request) -> Settings:
    return resources(request).settings


def database(request: Request) -> Iterator[Session]:
    with resources(request).session_factory() as session:
        yield session


def require_origin(
    request: Request, runtime_settings: Annotated[Settings, Depends(settings)]
) -> None:
    origin = request.headers.get("Origin")
    if origin not in runtime_settings.allowed_origins:
        raise ApiError(403, "ORIGIN_DENIED", "This request origin is not allowed.")


def require_session(
    request: Request,
    db: Annotated[Session, Depends(database)],
    runtime_settings: Annotated[Settings, Depends(settings)],
) -> DemoSession:
    return active_session(db, runtime_settings, request.cookies.get(SESSION_COOKIE))


def require_mutation_session(
    request: Request,
    db: Annotated[Session, Depends(database)],
    runtime_settings: Annotated[Settings, Depends(settings)],
    session: Annotated[DemoSession, Depends(require_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> DemoSession:
    require_origin(request, runtime_settings)
    validate_csrf(runtime_settings, session, csrf_token)
    return session


DatabaseSession = Annotated[Session, Depends(database)]
RuntimeSettings = Annotated[Settings, Depends(settings)]
RuntimeResource = Annotated[RuntimeResources, Depends(resources)]
CurrentSession = Annotated[DemoSession, Depends(require_session)]
MutationSession = Annotated[DemoSession, Depends(require_mutation_session)]
OriginCheck = Annotated[None, Depends(require_origin)]
