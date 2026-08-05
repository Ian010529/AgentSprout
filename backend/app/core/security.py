from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def keyed_hash(settings: Settings, purpose: str, value: str) -> str:
    key = settings.session_secret.get_secret_value().encode()
    message = f"{purpose}:{value}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def access_code_matches(settings: Settings, candidate: str) -> bool:
    expected = settings.studio_access_code.get_secret_value().encode()
    return hmac.compare_digest(expected, candidate.encode())


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
