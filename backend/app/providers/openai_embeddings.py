from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from openai import APITimeoutError, OpenAI

from app.core.config import Settings
from app.providers.contracts import ProviderTimeoutError


@dataclass(frozen=True, slots=True)
class EmbeddingCallRecord:
    model: str
    input_tokens: int
    total_tokens: int
    latency_ms: int
    timestamp: str


class OpenAIEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.embedding_model
        self._client = OpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )
        self._records: list[EmbeddingCallRecord] = []
        self._records_lock = threading.Lock()

    @property
    def model(self) -> str:
        return self._model

    @property
    def records(self) -> tuple[EmbeddingCallRecord, ...]:
        with self._records_lock:
            return tuple(self._records)

    def embed(self, texts: list[str]) -> list[list[float]]:
        started = time.perf_counter()
        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=texts,
                encoding_format="float",
            )
        except APITimeoutError as error:
            raise ProviderTimeoutError from error
        record = EmbeddingCallRecord(
            model=self._model,
            input_tokens=response.usage.prompt_tokens,
            total_tokens=response.usage.total_tokens,
            latency_ms=round((time.perf_counter() - started) * 1000),
            timestamp=datetime.now(UTC).isoformat(),
        )
        with self._records_lock:
            self._records.append(record)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]
