from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_required_secrets_fail_fast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "OPENAI_API_KEY",
        "STUDIO_ACCESS_CODE",
        "ADMIN_RESET_TOKEN",
        "SESSION_SECRET",
    ):
        monkeypatch.delenv(variable, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, data_dir=tmp_path)  # pyright: ignore[reportCallIssue]


def test_wildcard_origin_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Settings(  # pyright: ignore[reportCallIssue]
            _env_file=None,  # pyright: ignore[reportCallIssue]
            data_dir=tmp_path,
            allowed_origins=["*"],
            openai_api_key="test",
            studio_access_code="test-access",
            admin_reset_token="test-admin-token-value",
            session_secret="test-session-secret-value-at-least-32-characters",
        )
