from __future__ import annotations

import hmac
import math
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import access_code_matches, as_utc, keyed_hash, new_token, utc_now
from app.db.models import AuditEvent, DemoSession, RateLimitBucket
from app.domain.enums import Role
from app.domain.errors import ApiError

SESSION_COOKIE = "agentsprout_session"
ACCESS_SCOPE = "STUDIO_ACCESS_FAILURE"


def client_subject_hash(settings: Settings, client_host: str) -> str:
    return keyed_hash(settings, "access-client", client_host)


def access_retry_after(db: Session, settings: Settings, subject_hash: str) -> int | None:
    now = utc_now()
    bucket = db.scalar(
        select(RateLimitBucket).where(
            RateLimitBucket.subject_hash == subject_hash,
            RateLimitBucket.scope == ACCESS_SCOPE,
            RateLimitBucket.window_end > now,
        )
    )
    if bucket is None or bucket.count < settings.access_failed_limit:
        return None
    return max(1, math.ceil((as_utc(bucket.window_end) - now).total_seconds()))


def record_access_failure(db: Session, settings: Settings, subject_hash: str) -> None:
    now = utc_now()
    bucket = db.scalar(
        select(RateLimitBucket).where(
            RateLimitBucket.subject_hash == subject_hash,
            RateLimitBucket.scope == ACCESS_SCOPE,
            RateLimitBucket.window_end > now,
        )
    )
    if bucket is None:
        bucket = RateLimitBucket(
            id=str(uuid4()),
            subject_hash=subject_hash,
            scope=ACCESS_SCOPE,
            window_start=now,
            window_end=now + timedelta(minutes=settings.access_window_minutes),
            count=1,
        )
        db.add(bucket)
    else:
        bucket.count += 1
    db.commit()


def clear_access_failures(db: Session, subject_hash: str) -> None:
    db.execute(
        delete(RateLimitBucket).where(
            RateLimitBucket.subject_hash == subject_hash,
            RateLimitBucket.scope == ACCESS_SCOPE,
        )
    )


def validate_access_code(
    db: Session, settings: Settings, candidate: str, subject_hash: str
) -> None:
    retry_after = access_retry_after(db, settings, subject_hash)
    if retry_after is not None:
        raise ApiError(
            429,
            "ACCESS_RATE_LIMITED",
            "Too many access attempts. Try again later.",
            retryable=True,
            retry_after_seconds=retry_after,
        )
    if not access_code_matches(settings, candidate):
        record_access_failure(db, settings, subject_hash)
        raise ApiError(401, "ACCESS_DENIED", "The Studio access code is not valid.")
    clear_access_failures(db, subject_hash)


def create_session(db: Session, settings: Settings) -> tuple[DemoSession, str, str]:
    now = utc_now()
    raw_token = new_token()
    raw_csrf = new_token()
    session = DemoSession(
        id=str(uuid4()),
        token_hash=keyed_hash(settings, "session", raw_token),
        csrf_hash=keyed_hash(settings, "csrf", raw_csrf),
        role=Role.STUDENT.value,
        created_at=now,
        expires_at=now + timedelta(hours=settings.session_hours),
        last_seen_at=now,
        revoked_at=None,
    )
    db.add(session)
    db.commit()
    return session, raw_token, raw_csrf


def active_session(db: Session, settings: Settings, raw_token: str | None) -> DemoSession:
    if not raw_token:
        raise ApiError(401, "SESSION_REQUIRED", "Enter the Studio access code to continue.")
    token_hash = keyed_hash(settings, "session", raw_token)
    session = db.scalar(select(DemoSession).where(DemoSession.token_hash == token_hash))
    now = utc_now()
    if session is None or session.revoked_at is not None or as_utc(session.expires_at) <= now:
        raise ApiError(401, "SESSION_EXPIRED", "The Studio session has expired. Enter again.")
    return session


def rotate_csrf(db: Session, settings: Settings, session: DemoSession) -> str:
    raw_csrf = new_token()
    session.csrf_hash = keyed_hash(settings, "csrf", raw_csrf)
    session.last_seen_at = utc_now()
    db.commit()
    return raw_csrf


def validate_csrf(settings: Settings, session: DemoSession, raw_csrf: str | None) -> None:
    if not raw_csrf:
        raise ApiError(400, "CSRF_INVALID", "The request security token is missing or invalid.")
    received_hash = keyed_hash(settings, "csrf", raw_csrf)
    if not hmac.compare_digest(session.csrf_hash, received_hash):
        raise ApiError(400, "CSRF_INVALID", "The request security token is missing or invalid.")


def change_role(db: Session, session: DemoSession, role: Role) -> None:
    previous_role = session.role
    session.role = role.value
    session.last_seen_at = utc_now()
    db.add(
        AuditEvent(
            id=str(uuid4()),
            session_id=session.id,
            actor_type="DEMO_SESSION",
            action="SESSION_ROLE_CHANGED",
            target_type="DEMO_SESSION",
            target_id=session.id,
            result=f"{previous_role}_TO_{role.value}",
            created_at=utc_now(),
        )
    )
    db.commit()


def revoke_session(db: Session, session: DemoSession) -> None:
    session.revoked_at = utc_now()
    db.commit()
