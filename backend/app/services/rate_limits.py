"""Shared persisted rate-limit operations independent of Chat orchestration."""

from __future__ import annotations

import math
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import as_utc, keyed_hash, utc_now
from app.db.models import RateLimitBucket
from app.db.readiness import RuntimeResources
from app.domain.errors import ApiError

STUDIO_CHAT_SCOPE = "STUDIO_CHAT_HOUR"
GLOBAL_MODEL_SCOPE = "GLOBAL_MODEL_DAY"


def reserve_window(
    db: Session,
    *,
    subject_hash: str,
    scope: str,
    duration: timedelta,
    limit: int,
    error_code: str,
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
            error_code,
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
        reserve_window(
            db,
            subject_hash=keyed_hash(resources.settings, "global-model", "single-instance"),
            scope=GLOBAL_MODEL_SCOPE,
            duration=timedelta(days=1),
            limit=resources.settings.global_daily_model_limit,
            error_code="GLOBAL_MODEL_LIMITED",
            message="The demo's daily model-call limit has been reached.",
        )
