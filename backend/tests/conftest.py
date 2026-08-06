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
def client(settings: Settings, embedding_provider: FakeEmbeddingProvider) -> Iterator[TestClient]:
    migrate(settings)
    with TestClient(create_app(settings, embedding_provider=embedding_provider)) as test_client:
        yield test_client
