from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings


class ProviderTimeoutError(Exception):
    """Provider request exceeded the configured timeout."""


class RuntimeProviderError(Exception):
    def __init__(self, code: str, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class ProviderOutputError(Exception):
    """Provider returned no schema-valid, displayable output."""


@dataclass(frozen=True, slots=True)
class ProviderModels:
    online: str
    judge: str
    embedding: str
    moderation: str

    @classmethod
    def from_settings(cls, settings: Settings) -> ProviderModels:
        return cls(
            online=settings.online_model,
            judge=settings.judge_model,
            embedding=settings.embedding_model,
            moderation=settings.moderation_model,
        )


class ProviderAdapter(Protocol):
    """Configuration-only boundary; provider operations are added with their owning module."""

    @property
    def models(self) -> ProviderModels: ...


class EmbeddingProvider(Protocol):
    @property
    def model(self) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True, slots=True)
class ProviderCallRecord:
    operation: str
    model: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    latency_ms: int
    timestamp: str


@dataclass(frozen=True, slots=True)
class ModerationOutcome:
    flagged: bool
    categories: tuple[str, ...]
    call: ProviderCallRecord


@dataclass(frozen=True, slots=True)
class IntentOutcome:
    intent: str
    call: ProviderCallRecord


@dataclass(frozen=True, slots=True)
class GenerationOutcome:
    answer: str
    cited_chunk_ids: tuple[str, ...]
    call: ProviderCallRecord


class ChatProvider(Protocol):
    @property
    def online_model(self) -> str: ...

    @property
    def moderation_model(self) -> str: ...

    def moderate(self, text: str, operation: str) -> ModerationOutcome: ...

    def classify(self, message: str) -> IntentOutcome: ...

    def generate(
        self,
        *,
        message: str,
        evidence: list[dict[str, object]],
        audience_age: str,
        tone: str,
        response_length: str,
        custom_instructions: str,
        homework: bool,
    ) -> GenerationOutcome: ...
