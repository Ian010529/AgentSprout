from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from app.core.config import Settings
from app.db.migrations import alembic_config
from app.main import create_app
from app.providers.contracts import (
    GenerationOutcome,
    IntentOutcome,
    ModerationOutcome,
    ProviderCallRecord,
    ProviderOutputError,
    RuntimeProviderError,
)


class FakeEmbeddingProvider:
    model = "text-embedding-3-small"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.fail_next = False
        self.fail_on_call: int | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.fail_next or self.fail_on_call == len(self.calls):
            self.fail_next = False
            raise TimeoutError("synthetic provider timeout")
        terms = ("ocean", "climate", "current", "temperature", "coral", "whale")
        return [[float(text.lower().count(term)) + 0.001 for term in terms] for text in texts]


class FakeChatProvider:
    online_model = "gpt-4o-mini-2024-07-18"
    moderation_model = "omni-moderation-latest"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.intent = "KNOWLEDGE"
        self.input_flagged = False
        self.output_flagged = False
        self.invalid_citation = False
        self.fail_code: str | None = None
        self.malformed_output = False

    def _record(self, operation: str, model: str) -> ProviderCallRecord:
        return ProviderCallRecord(
            operation=operation,
            model=model,
            input_tokens=12 if model == self.online_model else 0,
            output_tokens=7 if model == self.online_model else 0,
            reasoning_tokens=0,
            latency_ms=3,
            timestamp="2026-08-06T00:00:00+00:00",
        )

    def moderate(self, text: str, operation: str) -> ModerationOutcome:
        self.calls.append((operation, text))
        flagged = self.input_flagged if operation == "INPUT_MODERATION" else self.output_flagged
        return ModerationOutcome(
            flagged=flagged,
            categories=("violence",) if flagged else (),
            call=self._record(operation, self.moderation_model),
        )

    def classify(self, message: str) -> IntentOutcome:
        self.calls.append(("INTENT_CLASSIFICATION", message))
        if self.fail_code:
            raise RuntimeProviderError(self.fail_code, True)
        return IntentOutcome(
            intent=self.intent,
            call=self._record("INTENT_CLASSIFICATION", self.online_model),
        )

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
    ) -> GenerationOutcome:
        del audience_age, tone, response_length, custom_instructions
        self.calls.append(("GENERATION", message))
        if self.malformed_output:
            raise ProviderOutputError
        chunk_id = "not-allowed" if self.invalid_citation else str(evidence[0]["chunk_id"])
        answer = (
            "Ocean currents move heat around Earth. Here is a hint: identify where warm "
            "water travels. What pattern do you notice?"
            if homework
            else "Ocean currents redistribute heat and influence regional climate."
        )
        return GenerationOutcome(
            answer=answer,
            cited_chunk_ids=(chunk_id,),
            call=self._record("GENERATION", self.online_model),
        )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(  # pyright: ignore[reportCallIssue]
        _env_file=None,  # pyright: ignore[reportCallIssue]
        app_env="test",
        data_dir=tmp_path / "runtime",
        allowed_origins=["http://testserver"],
        openai_api_key="test-key-not-used-by-m1",
        studio_access_code="test-access",
        admin_reset_token="test-admin-token-value",
        session_secret="test-session-secret-value-at-least-32-characters",
    )


def migrate(settings: Settings) -> None:
    settings.create_runtime_directories()
    config: Config = alembic_config()
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")


@pytest.fixture
def embedding_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def chat_provider() -> FakeChatProvider:
    return FakeChatProvider()


@pytest.fixture
def client(
    settings: Settings,
    embedding_provider: FakeEmbeddingProvider,
    chat_provider: FakeChatProvider,
) -> Iterator[TestClient]:
    migrate(settings)
    with TestClient(
        create_app(
            settings,
            embedding_provider=embedding_provider,
            chat_provider=chat_provider,
        )
    ) as test_client:
        yield test_client
