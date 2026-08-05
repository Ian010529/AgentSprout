from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.api.dependencies import (
    CurrentSession,
    DatabaseSession,
    MutationSession,
    OriginCheck,
    RuntimeSettings,
)
from app.api.schemas import AccessRequest, RoleUpdate, SessionResponse, SessionView
from app.core.security import as_utc
from app.db.models import DemoSession
from app.domain.enums import Role
from app.services.sessions import (
    SESSION_COOKIE,
    change_role,
    client_subject_hash,
    create_session,
    revoke_session,
    rotate_csrf,
    validate_access_code,
)

router = APIRouter(prefix="/studio", tags=["studio-session"])


def session_response(session: DemoSession, csrf_token: str) -> SessionResponse:
    return SessionResponse(
        session=SessionView(role=Role(session.role), expires_at=as_utc(session.expires_at)),
        csrf_token=csrf_token,
    )


@router.post("/access", response_model=SessionResponse)
def access(
    payload: AccessRequest,
    request: Request,
    response: Response,
    db: DatabaseSession,
    runtime_settings: RuntimeSettings,
    _origin: OriginCheck,
) -> SessionResponse:
    client_host = request.client.host if request.client is not None else "unknown"
    subject_hash = client_subject_hash(runtime_settings, client_host)
    validate_access_code(db, runtime_settings, payload.access_code, subject_hash)
    session, raw_token, raw_csrf = create_session(db, runtime_settings)
    is_production = runtime_settings.app_env == "production"
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_token,
        max_age=runtime_settings.session_hours * 3600,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        path="/",
    )
    return session_response(session, raw_csrf)


@router.get("/session", response_model=SessionResponse)
def restore_session(
    db: DatabaseSession,
    runtime_settings: RuntimeSettings,
    session: CurrentSession,
) -> SessionResponse:
    return session_response(session, rotate_csrf(db, runtime_settings, session))


@router.patch("/session/role", response_model=SessionResponse)
def update_role(
    payload: RoleUpdate,
    db: DatabaseSession,
    runtime_settings: RuntimeSettings,
    session: MutationSession,
) -> SessionResponse:
    change_role(db, session, payload.role)
    return session_response(session, rotate_csrf(db, runtime_settings, session))


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(
    response: Response,
    db: DatabaseSession,
    runtime_settings: RuntimeSettings,
    session: MutationSession,
) -> Response:
    revoke_session(db, session)
    is_production = runtime_settings.app_env == "production"
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=is_production,
        httponly=True,
        samesite="none" if is_production else "lax",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
