from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    data_dir: Path = Path("./data")
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    openai_api_key: SecretStr
    studio_access_code: SecretStr = Field(min_length=8)
    admin_reset_token: SecretStr = Field(min_length=16)
    session_secret: SecretStr = Field(min_length=32)

    online_model: str = "gpt-4o-mini-2024-07-18"
    judge_model: str = "gpt-4.1-mini-2025-04-14"
    embedding_model: str = "text-embedding-3-small"
    moderation_model: str = "omni-moderation-latest"

    rag_top_k: int = Field(default=4, ge=1, le=20)
    rag_min_similarity: float = Field(default=0.35, ge=0, le=1)
    openai_timeout_seconds: int = Field(default=20, ge=1, le=120)
    openai_max_retries: int = Field(default=2, ge=0, le=5)
    studio_retention_days: int = Field(default=30, ge=1, le=365)
    public_hourly_limit: int = Field(default=10, ge=1)
    public_daily_limit: int = Field(default=20, ge=1)
    studio_hourly_limit: int = Field(default=60, ge=1)
    global_daily_model_limit: int = Field(default=300, ge=1)
    daily_evaluation_limit: int = Field(default=5, ge=1)
    daily_ingestion_limit: int = Field(default=5, ge=1)
    session_hours: int = Field(default=8, ge=1, le=24)
    access_failed_limit: int = Field(default=5, ge=1, le=20)
    access_window_minutes: int = Field(default=15, ge=1, le=60)
    idempotency_hours: int = Field(default=24, ge=1, le=72)

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        if not origins:
            raise ValueError("ALLOWED_ORIGINS must contain at least one exact origin")
        for origin in origins:
            if origin == "*" or not origin.startswith(("http://", "https://")):
                raise ValueError("ALLOWED_ORIGINS must contain exact HTTP(S) origins")
        return origins

    @property
    def resolved_data_dir(self) -> Path:
        if self.data_dir.is_absolute():
            return self.data_dir
        return (PROJECT_ROOT / self.data_dir).resolve()

    @property
    def database_path(self) -> Path:
        return self.resolved_data_dir / "app.db"

    @property
    def database_url(self) -> str:
        return f"sqlite+pysqlite:///{self.database_path}"

    @property
    def chroma_path(self) -> Path:
        return self.resolved_data_dir / "chroma"

    @property
    def uploads_path(self) -> Path:
        return self.resolved_data_dir / "uploads"

    def create_runtime_directories(self) -> None:
        self.resolved_data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.uploads_path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
