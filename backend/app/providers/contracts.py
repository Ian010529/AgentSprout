from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings


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
