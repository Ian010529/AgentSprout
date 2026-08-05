from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings as ChromaSettings
from sqlalchemy import Engine, text

from app.core.config import Settings
from app.db.migrations import migrations_are_current


@dataclass(frozen=True, slots=True)
class RuntimeResources:
    settings: Settings
    engine: Engine
    chroma: ClientAPI


def create_chroma_client(settings: Settings) -> ClientAPI:
    return chromadb.PersistentClient(
        path=str(settings.chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _check_sqlite(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _check_uploads(path: Path) -> None:
    with tempfile.NamedTemporaryFile(dir=path, prefix=".ready-", delete=True):
        pass


def readiness_checks(resources: RuntimeResources) -> dict[str, str]:
    checks: dict[str, str] = {}

    try:
        _check_sqlite(resources.engine)
        checks["sqlite"] = "ok"
    except Exception:
        checks["sqlite"] = "failed"

    try:
        resources.chroma.heartbeat()
        checks["chroma"] = "ok"
    except Exception:
        checks["chroma"] = "failed"

    try:
        _check_uploads(resources.settings.uploads_path)
        checks["uploads"] = "ok"
    except Exception:
        checks["uploads"] = "failed"

    try:
        checks["migrations"] = "ok" if migrations_are_current(resources.engine) else "failed"
    except Exception:
        checks["migrations"] = "failed"

    return checks
