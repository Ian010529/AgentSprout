#!/usr/bin/env python3
"""Opt-in real OpenAI embedding and NOAA retrieval smoke test for M3."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings
from app.db.migrations import alembic_config
from app.main import create_app
from app.providers.openai_embeddings import OpenAIEmbeddingProvider
from app.services.knowledge import retrieve

ORIGIN = {"Origin": "http://testserver"}
SOURCE = PROJECT_ROOT / "examples" / "knowledge" / "ocean-literacy-2024.pdf"


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def main() -> int:
    if os.environ.get("RUN_LIVE_TESTS") != "1":
        return fail("Set RUN_LIVE_TESTS=1 to authorize the real provider smoke test.")
    if not (PROJECT_ROOT / ".env").is_file():
        return fail(
            "Create the project .env with OPENAI_API_KEY before running this test."
        )
    if not SOURCE.is_file():
        return fail("Run scripts/download_noaa_source.py before the live smoke test.")

    with tempfile.TemporaryDirectory(prefix="agentsprout-live-m3-") as directory:
        settings = Settings(  # pyright: ignore[reportCallIssue]
            _env_file=PROJECT_ROOT / ".env",  # pyright: ignore[reportCallIssue]
            app_env="test",
            data_dir=Path(directory),
            allowed_origins=["http://testserver"],
            studio_access_code="live-test-access",
            admin_reset_token="live-test-admin-token",
            session_secret="live-test-session-secret-at-least-32-characters",
        )
        settings.create_runtime_directories()
        config: Config = alembic_config()
        config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(config, "head")

        provider = OpenAIEmbeddingProvider(settings)
        started = time.perf_counter()
        with TestClient(create_app(settings, embedding_provider=provider)) as client:
            access = client.post(
                "/api/v1/studio/access",
                json={"access_code": "live-test-access"},
                headers=ORIGIN,
            )
            access.raise_for_status()
            csrf = str(access.json()["csrf_token"])
            headers = {**ORIGIN, "X-CSRF-Token": csrf}
            created = client.post(
                "/api/v1/studio/agents",
                headers={**headers, "Idempotency-Key": "live-m3-create-agent"},
                json={
                    "template": "KNOWLEDGE_EXPLORER",
                    "project_name": "Ocean Explorer",
                    "problem_to_solve": "Help learners understand ocean science from evidence.",
                    "intended_users": "Students learning ocean science",
                    "audience_age": "AGE_12_17",
                    "success_goal": "Give clear answers grounded in the uploaded source.",
                    "welcome_message": "What would you like to discover about the ocean?",
                    "tone": "CURIOUS",
                    "response_length": "BALANCED",
                    "custom_instructions": "",
                },
            )
            created.raise_for_status()
            version_id = str(created.json()["version"]["id"])
            with SOURCE.open("rb") as source:
                upload = client.post(
                    f"/api/v1/studio/versions/{version_id}/knowledge",
                    headers={**headers, "Idempotency-Key": "live-m3-noaa-upload"},
                    files={"file": (SOURCE.name, source, "application/pdf")},
                )
            upload.raise_for_status()
            job_id = str(upload.json()["job_id"])
            deadline = time.monotonic() + 180
            job: dict[str, object] = {}
            while time.monotonic() < deadline:
                job_response = client.get(f"/api/v1/studio/ingestion-jobs/{job_id}")
                job_response.raise_for_status()
                job = job_response.json()
                if job["state"] in {"READY", "FAILED"}:
                    break
                time.sleep(0.2)
            if job.get("state") != "READY":
                return fail(
                    f"Live ingestion failed safely: {job.get('error_code', 'TIMEOUT')}"
                )
            results = retrieve(
                client.app.state.resources,
                version_id,
                "Why is the ocean important to Earth's climate?",
            )
            if not results:
                return fail(
                    "Live retrieval returned no result above the configured threshold."
                )

        elapsed_ms = round((time.perf_counter() - started) * 1000)
        report = {
            "timestamp": provider.records[-1].timestamp,
            "model": provider.model,
            "elapsed_ms": elapsed_ms,
            "provider_calls": [asdict(record) for record in provider.records],
            "retrieved": [
                {"page": item.page_number, "similarity": round(item.similarity, 4)}
                for item in results
            ],
        }
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
