from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

from app.api.errors import ApiError
from app.api.schemas import ChatResultView, PublicRunCreateResponse, ResetResponse
from app.core.security import as_utc, utc_now


@dataclass
class PublicMemoryRun:
    token_hash: str
    expires_at: datetime
    prompt: str | None
    result: ChatResultView | None = None


@dataclass
class PublicIdempotency:
    request_hash: str
    response: PublicRunCreateResponse
    expires_at: datetime


class TransientStore:
    """Process-only public content and short browser-retry state."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._runs: dict[str, PublicMemoryRun] = {}
        self._public_keys: dict[str, PublicIdempotency] = {}
        self._reset_keys: dict[str, ResetResponse] = {}

    def _purge(self, now: datetime) -> None:
        self._runs = {
            key: value for key, value in self._runs.items() if as_utc(value.expires_at) > now
        }
        self._public_keys = {
            key: value for key, value in self._public_keys.items() if as_utc(value.expires_at) > now
        }

    def add_run(self, run_id: str, record: PublicMemoryRun) -> None:
        with self._lock:
            self._purge(utc_now())
            self._runs[run_id] = record

    def claim_prompt(self, run_id: str) -> str | None:
        with self._lock:
            self._purge(utc_now())
            record = self._runs.get(run_id)
            if record is None:
                return None
            prompt = record.prompt
            record.prompt = None
            return prompt

    def save_result(self, run_id: str, result: ChatResultView | None) -> None:
        with self._lock:
            self._purge(utc_now())
            record = self._runs.get(run_id)
            if record is not None:
                record.prompt = None
                record.result = result

    def get_run(self, run_id: str, token_hash: str) -> PublicMemoryRun:
        with self._lock:
            self._purge(utc_now())
            record = self._runs.get(run_id)
            if record is None or not hmac.compare_digest(record.token_hash, token_hash):
                raise ApiError(404, "RUN_EXPIRED", "This public result is no longer available.")
            return PublicMemoryRun(
                token_hash=record.token_hash,
                expires_at=record.expires_at,
                prompt=None,
                result=record.result,
            )

    def public_replay(self, key_hash: str, request_hash: str) -> PublicRunCreateResponse | None:
        with self._lock:
            self._purge(utc_now())
            record = self._public_keys.get(key_hash)
            if record is None:
                return None
            if not hmac.compare_digest(record.request_hash, request_hash):
                raise ApiError(
                    409,
                    "IDEMPOTENCY_KEY_REUSED",
                    "This request key was already used for another public message.",
                )
            return record.response

    def save_public_key(
        self,
        key_hash: str,
        request_hash: str,
        response: PublicRunCreateResponse,
        expires_at: datetime,
    ) -> None:
        with self._lock:
            self._public_keys[key_hash] = PublicIdempotency(
                request_hash=request_hash,
                response=response,
                expires_at=expires_at,
            )

    def reset_replay(self, key_hash: str) -> ResetResponse | None:
        with self._lock:
            return self._reset_keys.get(key_hash)

    def save_reset(self, key_hash: str, response: ResetResponse) -> None:
        with self._lock:
            self._reset_keys[key_hash] = response

    def clear_runs(self) -> None:
        with self._lock:
            self._runs.clear()
            self._public_keys.clear()
