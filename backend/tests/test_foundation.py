from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings
from app.db.engine import create_sqlite_engine
from app.db.migrations import current_revision, head_revision
from app.main import create_app
from tests.conftest import migrate


def test_health_contract(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "agentsprout-api"}
    assert response.headers["X-Request-ID"]


def test_ready_contract(client: TestClient) -> None:
    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"sqlite": "ok", "chroma": "ok", "uploads": "ok", "migrations": "ok"},
    }


def test_ready_reports_missing_migration(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["migrations"] == "failed"


def test_sqlite_pragmas_and_migration(settings: Settings) -> None:
    migrate(settings)
    engine = create_sqlite_engine(settings)

    with engine.connect() as connection:
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()

    assert foreign_keys == 1
    assert str(journal_mode).lower() == "wal"
    assert current_revision(engine) == head_revision() == "0001_foundation"


def test_chroma_persists_across_clients(tmp_path: Path) -> None:
    path = tmp_path / "chroma"
    first = chromadb.PersistentClient(
        path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
    )
    collection = first.get_or_create_collection("foundation_test")
    collection.add(ids=["one"], documents=["Ocean evidence"], embeddings=[[0.1, 0.2]])

    second = chromadb.PersistentClient(
        path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
    )
    assert second.get_collection("foundation_test").count() == 1
