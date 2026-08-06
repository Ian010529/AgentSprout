#!/usr/bin/env python3
"""Opt-in real OpenAI grounded answer, moderation, and PII-stop smoke test for M4."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import UTC, datetime
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
from app.providers.contracts import (
    GenerationOutcome,
    IntentOutcome,
    ModerationOutcome,
)
from app.providers.openai_chat import OpenAIChatProvider
from app.providers.openai_embeddings import OpenAIEmbeddingProvider

ORIGIN = {"Origin": "http://testserver"}
SOURCE = PROJECT_ROOT / "examples" / "knowledge" / "ocean-literacy-2024.pdf"


class RecordingChatProvider:
    def __init__(self, inner: OpenAIChatProvider) -> None:
        self.inner = inner
        self.operations: list[str] = []

    @property
    def online_model(self) -> str:
        return self.inner.online_model

    @property
    def moderation_model(self) -> str:
        return self.inner.moderation_model

    def moderate(self, text: str, operation: str) -> ModerationOutcome:
        self.operations.append(operation)
        return self.inner.moderate(text, operation)

    def classify(self, message: str) -> IntentOutcome:
        self.operations.append("INTENT_CLASSIFICATION")
        return self.inner.classify(message)

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
        self.operations.append("GENERATION")
        return self.inner.generate(
            message=message,
            evidence=evidence,
            audience_age=audience_age,
            tone=tone,
            response_length=response_length,
            custom_instructions=custom_instructions,
            homework=homework,
        )


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

    with tempfile.TemporaryDirectory(prefix="agentsprout-live-m4-") as directory:
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

        embedding_provider = OpenAIEmbeddingProvider(settings)
        chat_provider = RecordingChatProvider(OpenAIChatProvider(settings))
        started_at = datetime.now(UTC)
        started_clock = time.perf_counter()
        with TestClient(
            create_app(
                settings,
                embedding_provider=embedding_provider,
                chat_provider=chat_provider,
            )
        ) as client:
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
                headers={**headers, "Idempotency-Key": "live-m4-create-agent"},
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
                    headers={**headers, "Idempotency-Key": "live-m4-noaa-upload"},
                    files={"file": (SOURCE.name, source, "application/pdf")},
                )
            upload.raise_for_status()
            job_id = str(upload.json()["job_id"])
            deadline = time.monotonic() + 180
            job: dict[str, object] = {}
            while time.monotonic() < deadline:
                job = client.get(f"/api/v1/studio/ingestion-jobs/{job_id}").json()
                if job["state"] in {"READY", "FAILED"}:
                    break
                time.sleep(0.2)
            if job.get("state") != "READY":
                return fail(
                    "Live knowledge ingestion failed safely: "
                    f"{job.get('error_code', 'TIMEOUT')}"
                )

            run_start = client.post(
                f"/api/v1/studio/versions/{version_id}/runs",
                headers={**headers, "Idempotency-Key": "live-m4-grounded-run"},
                json={"message": "How do ocean currents affect Earth's climate?"},
            )
            run_start.raise_for_status()
            run_id = str(run_start.json()["run_id"])
            deadline = time.monotonic() + 30
            run: dict[str, object] = {}
            while time.monotonic() < deadline:
                run = client.get(f"/api/v1/studio/runs/{run_id}").json()
                if run["status"] in {"COMPLETED", "FAILED"}:
                    break
                time.sleep(0.2)
            result = run.get("result")
            if (
                run.get("status") != "COMPLETED"
                or not isinstance(result, dict)
                or result.get("type") != "ANSWERED"
            ):
                return fail(f"Live grounded run failed safely: {run.get('safe_error')}")
            citations = result.get("citations")
            if not isinstance(citations, list) or not citations:
                return fail("Live grounded answer returned no validated citation.")

            calls_before_pii = len(chat_provider.operations)
            canary = "live-pii-canary-918@example.test"
            pii = client.post(
                f"/api/v1/studio/versions/{version_id}/runs",
                headers={**headers, "Idempotency-Key": "live-m4-pii-run"},
                json={"message": f"My email is {canary}"},
            )
            pii.raise_for_status()
            pii_result = client.get(
                f"/api/v1/studio/runs/{pii.json()['run_id']}"
            ).json()
            if pii_result["result"]["type"] != "BLOCKED":
                return fail("The live PII canary was not blocked.")
            pii_provider_calls = len(chat_provider.operations) - calls_before_pii
            if pii_provider_calls != 0:
                return fail("The live PII canary reached a provider boundary.")
            if canary.encode() in settings.database_path.read_bytes():
                return fail("The live PII canary was found in SQLite.")

            changed = client.patch(
                "/api/v1/studio/session/role",
                headers=headers,
                json={"role": "TEACHER"},
            )
            changed.raise_for_status()
            trace = client.get(f"/api/v1/studio/runs/{run_id}/trace").json()

        report = {
            "timestamp": started_at.isoformat(),
            "models": trace["models"],
            "elapsed_ms": round((time.perf_counter() - started_clock) * 1000),
            "provider_operations": chat_provider.operations,
            "usage": trace["usage"],
            "result_type": result["type"],
            "citation_pages": [item["page_number"] for item in citations],
            "pii_provider_calls": pii_provider_calls,
            "pii_persisted": False,
        }
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
