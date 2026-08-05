from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    retryable: bool = False
    retry_after_seconds: int | None = None
    field_errors: dict[str, str] = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)
