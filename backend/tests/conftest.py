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
def client(settings: Settings) -> Iterator[TestClient]:
    migrate(settings)
    with TestClient(create_app(settings)) as test_client:
        yield test_client
