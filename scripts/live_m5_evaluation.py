#!/usr/bin/env python3
"""Opt-in real OpenAI 16-case teacher evaluation acceptance for M5."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings
from app.db.migrations import alembic_config
from app.main import create_app
from app.providers.contracts import JudgeOutcome
from app.providers.openai_chat import OpenAIChatProvider
from app.providers.openai_embeddings import OpenAIEmbeddingProvider
from app.providers.openai_judge import OpenAIJudgeProvider
from live_m4_smoke import RecordingChatProvider

ORIGIN = {"Origin": "http://testserver"}
SOURCE = PROJECT_ROOT / "examples" / "knowledge" / "ocean-literacy-2024.pdf"


class RecordingJudgeProvider:
    def __init__(self, inner: OpenAIJudgeProvider) -> None:
        self.inner = inner
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.lock = Lock()

    @property
    def model(self) -> str:
        return self.inner.model

    def judge(
        self,
        *,
        safe_case_prompt: str,
        expected_behavior: str,
        audience_age: str,
        displayed_output: str,
        evidence: list[dict[str, object]],
    ) -> JudgeOutcome:
        with self.lock:
            self.calls += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            return self.inner.judge(
                safe_case_prompt=safe_case_prompt,
                expected_behavior=expected_behavior,
                audience_age=audience_age,
                displayed_output=displayed_output,
                evidence=evidence,
            )
        finally:
            with self.lock:
                self.active -= 1


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def main() -> int:
    if os.environ.get("RUN_LIVE_TESTS") != "1":
        return fail("Set RUN_LIVE_TESTS=1 to authorize the real 16-case evaluation.")
    if not (PROJECT_ROOT / ".env").is_file():
        return fail("Create the project .env with OPENAI_API_KEY before this test.")
    if not SOURCE.is_file():
        return fail("Run scripts/download_noaa_source.py before the live evaluation.")

    with tempfile.TemporaryDirectory(prefix="agentsprout-live-m5-") as directory:
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

        embedding = OpenAIEmbeddingProvider(settings)
        chat = RecordingChatProvider(OpenAIChatProvider(settings))
        judge = RecordingJudgeProvider(OpenAIJudgeProvider(settings))
        started_at = datetime.now(UTC)
        total_started = time.perf_counter()
        with TestClient(
            create_app(
                settings,
                embedding_provider=embedding,
                chat_provider=chat,
                judge_provider=judge,
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
                headers={**headers, "Idempotency-Key": "live-m5-create-agent"},
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
                    headers={**headers, "Idempotency-Key": "live-m5-noaa-upload"},
                    files={"file": (SOURCE.name, source, "application/pdf")},
                )
            upload.raise_for_status()
            job_id = str(upload.json()["job_id"])
            ingestion_deadline = time.monotonic() + 180
            job: dict[str, object] = {}
            while time.monotonic() < ingestion_deadline:
                job = client.get(f"/api/v1/studio/ingestion-jobs/{job_id}").json()
                if job.get("state") in {"READY", "FAILED"}:
                    break
                time.sleep(0.2)
            if job.get("state") != "READY":
                return fail(
                    "Live knowledge ingestion failed safely: "
                    f"{job.get('error_code', 'TIMEOUT')}"
                )

            submitted = client.post(
                f"/api/v1/studio/versions/{version_id}/submit",
                headers={**headers, "Idempotency-Key": "live-m5-submit"},
            )
            submitted.raise_for_status()
            role = client.patch(
                "/api/v1/studio/session/role",
                headers=headers,
                json={"role": "TEACHER"},
            )
            role.raise_for_status()
            headers["X-CSRF-Token"] = str(role.json()["csrf_token"])

            evaluation_started = time.perf_counter()
            started = client.post(
                f"/api/v1/studio/versions/{version_id}/evaluations",
                headers={**headers, "Idempotency-Key": "live-m5-evaluation"},
            )
            started.raise_for_status()
            run_id = str(started.json()["evaluation_run_id"])
            evaluation_deadline = time.monotonic() + 300
            run: dict[str, object] = {}
            while time.monotonic() < evaluation_deadline:
                response = client.get(f"/api/v1/studio/evaluations/{run_id}")
                response.raise_for_status()
                run = response.json()
                if run.get("state") in {"COMPLETED", "FAILED"}:
                    break
                time.sleep(0.5)
            evaluation_ms = round((time.perf_counter() - evaluation_started) * 1000)
            if run.get("state") != "COMPLETED":
                return fail(
                    f"Live evaluation failed safely: {run.get('safe_error', 'TIMEOUT')}"
                )
            case_response = client.get(f"/api/v1/studio/evaluations/{run_id}/cases")
            case_response.raise_for_status()
            cases = case_response.json()["cases"]
            details: list[dict[str, object]] = []
            for case in cases:
                if case["passed"]:
                    continue
                detail_response = client.get(
                    f"/api/v1/studio/evaluation-cases/{case['id']}"
                )
                detail_response.raise_for_status()
                detail = detail_response.json()
                details.append(
                    {
                        "case_key": case["case_key"],
                        "category": case["category"],
                        "actual_result_type": case["actual_result_type"],
                        "failed_checks": [
                            key
                            for key, passed in detail["deterministic_checks"].items()
                            if not passed
                        ],
                        "judge": detail["judge"],
                        "safe_error_code": case["safe_error_code"],
                    }
                )

            canaries = (b"@example.test", b"202-555-0187", b"742 Evergreen Street")
            persisted = b"".join(
                path.read_bytes()
                for path in settings.resolved_data_dir.rglob("*")
                if path.is_file()
            )
            if any(canary in persisted for canary in canaries):
                return fail(
                    "A synthetic evaluation PII canary reached persistent storage."
                )

        category_total = Counter(case["category"] for case in cases)
        category_passed = Counter(case["category"] for case in cases if case["passed"])
        report = {
            "timestamp": started_at.isoformat(),
            "models": run["models"],
            "evaluation_elapsed_ms": evaluation_ms,
            "total_elapsed_ms": round((time.perf_counter() - total_started) * 1000),
            "progress": run["progress"],
            "metrics": run["metrics"],
            "release_eligible": run["release_eligible"],
            "usage": run["usage"],
            "provider_operation_counts": dict(Counter(chat.operations)),
            "judge_calls": judge.calls,
            "judge_max_concurrency": judge.max_active,
            "categories": {
                category: {
                    "passed": category_passed[category],
                    "total": category_total[category],
                }
                for category in sorted(category_total)
            },
            "failed_cases": details,
            "pii_persisted": False,
        }
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
