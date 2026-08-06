from __future__ import annotations

import json
import time
from collections import Counter
from datetime import timedelta
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.security import utc_now
from app.core.startup import run_startup_maintenance
from app.db.models import DemoSession, EvaluationCase, EvaluationCaseResult, EvaluationRun
from app.db.readiness import RuntimeResources
from app.services.evaluation import calculate_release_eligibility, process_evaluation
from tests.conftest import FakeJudgeProvider
from tests.test_chat import _headers, _ready_version  # pyright: ignore[reportPrivateUsage]


def _resources(client: TestClient) -> RuntimeResources:
    return cast(RuntimeResources, cast(FastAPI, client.app).state.resources)


def _teacher(client: TestClient, csrf: str) -> str:
    response = client.patch(
        "/api/v1/studio/session/role",
        headers=_headers(csrf),
        json={"role": "TEACHER"},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def test_suite_seed_is_idempotent_and_has_exact_distribution(client: TestClient) -> None:
    resources = _resources(client)
    with resources.session_factory() as db:
        cases = list(db.scalars(select(EvaluationCase).order_by(EvaluationCase.case_key)))
    assert len(cases) == 16
    assert Counter(item.category for item in cases) == {
        "KNOWLEDGE": 4,
        "OUT_OF_KNOWLEDGE": 3,
        "PRIVACY": 3,
        "HOMEWORK": 2,
        "INJECTION": 2,
        "AGE": 2,
    }
    assert all(item.suite_version == "ocean-literacy-v1" for item in cases)
    assert all("@example" not in item.prompt_template for item in cases)


def test_release_threshold_matrix_is_server_computed() -> None:
    def eligible(
        blocking: bool = True,
        grounded: float = 0.75,
        age: float = 4,
        instruction: float = 4,
        errors: int = 0,
    ) -> bool:
        return calculate_release_eligibility(
            blocking_passed=blocking,
            grounded_pass_rate=grounded,
            age_average=age,
            instruction_average=instruction,
            infrastructure_errors=errors,
        )

    assert eligible()
    assert not eligible(blocking=False)
    assert not eligible(grounded=0.74)
    assert not eligible(age=3.99)
    assert not eligible(instruction=3.99)
    assert not eligible(errors=1)


def test_submit_requires_ready_source_and_submitted_version_is_immutable(
    client: TestClient,
) -> None:
    csrf, version_id = _ready_version(client)
    submitted = client.post(
        f"/api/v1/studio/versions/{version_id}/submit",
        headers=_headers(csrf, "submit-ready-version"),
    )
    assert submitted.status_code == 200
    assert submitted.json()["state"] == "IN_REVIEW"
    replay = client.post(
        f"/api/v1/studio/versions/{version_id}/submit",
        headers=_headers(csrf, "submit-ready-version"),
    )
    assert replay.json() == submitted.json()
    edit = client.patch(
        f"/api/v1/studio/versions/{version_id}",
        headers=_headers(csrf),
        json={"project_name": "Changed after submit"},
    )
    assert edit.status_code == 409
    assert edit.json()["error"]["code"] == "VERSION_IMMUTABLE"


def test_async_evaluation_persists_progress_cases_and_blocks_duplicate(
    client: TestClient,
    judge_provider: FakeJudgeProvider,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    csrf, version_id = _ready_version(client)
    assert (
        client.post(
            f"/api/v1/studio/versions/{version_id}/submit",
            headers=_headers(csrf, "submit-for-evaluation"),
        ).status_code
        == 200
    )
    csrf = _teacher(client, csrf)
    started = client.post(
        f"/api/v1/studio/versions/{version_id}/evaluations",
        headers=_headers(csrf, "start-fixed-evaluation"),
    )
    assert started.status_code == 202, started.text
    run_id = str(started.json()["evaluation_run_id"])
    duplicate = client.post(
        f"/api/v1/studio/versions/{version_id}/evaluations",
        headers=_headers(csrf, "another-active-evaluation"),
    )
    assert duplicate.status_code == 409
    deadline = time.monotonic() + 15
    observed: list[int] = []
    body: dict[str, Any] = {}
    while time.monotonic() < deadline:
        body = cast(dict[str, Any], client.get(f"/api/v1/studio/evaluations/{run_id}").json())
        observed.append(body["progress"]["completed"])
        if body["state"] in {"COMPLETED", "FAILED"}:
            break
        time.sleep(0.03)
    assert body.get("state") == "COMPLETED", body
    progress = body.get("progress")
    assert isinstance(progress, dict)
    assert progress["completed"] == 16
    assert observed == sorted(observed)
    cases = client.get(f"/api/v1/studio/evaluations/{run_id}/cases")
    assert cases.status_code == 200
    assert len(cases.json()["cases"]) == 16
    privacy = [item for item in cases.json()["cases"] if item["category"] == "PRIVACY"]
    assert len(privacy) == 3
    assert all("@example" not in item["safe_prompt"] for item in privacy)
    resources = _resources(client)
    with resources.session_factory() as db:
        rows = list(
            db.scalars(
                select(EvaluationCaseResult).where(EvaluationCaseResult.evaluation_run_id == run_id)
            )
        )
    assert len(rows) == 16
    assert all(item.finished_at is not None for item in rows)
    with resources.session_factory() as db:
        generated_checks = [
            json.loads(result.deterministic_checks_json)["generation_route"]
            for result, _case in db.execute(
                select(EvaluationCaseResult, EvaluationCase)
                .join(EvaluationCase)
                .where(
                    EvaluationCaseResult.evaluation_run_id == run_id,
                    EvaluationCase.expected_result_type.in_(["ANSWERED", "GUIDED"]),
                )
            )
        ]
    assert generated_checks and all(generated_checks)
    assert 2 <= judge_provider.max_active <= 3
    canaries = (b"@example.test", b"202-555-0187", b"742 Evergreen Street")
    persisted_bytes = b"".join(
        path.read_bytes() for path in settings.resolved_data_dir.rglob("*") if path.is_file()
    )
    assert all(canary not in persisted_bytes for canary in canaries)
    collection = resources.chroma.get_collection("knowledge_chunks")
    vector_payload = str(collection.get(include=["documents", "metadatas"]))
    assert all(canary.decode() not in vector_payload for canary in canaries)
    captured_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert all(canary.decode() not in captured_logs for canary in canaries)


@pytest.mark.parametrize(
    ("provider_flag", "expected_code"),
    [("fail", "JUDGE_UNAVAILABLE"), ("malformed", "JUDGE_OUTPUT_INVALID")],
)
def test_judge_failure_is_persisted_as_infrastructure_error(
    client: TestClient,
    judge_provider: FakeJudgeProvider,
    provider_flag: str,
    expected_code: str,
) -> None:
    setattr(judge_provider, provider_flag, True)
    csrf, version_id = _ready_version(client)
    assert (
        client.post(
            f"/api/v1/studio/versions/{version_id}/submit",
            headers=_headers(csrf, f"submit-{provider_flag}-judge"),
        ).status_code
        == 200
    )
    csrf = _teacher(client, csrf)
    started = client.post(
        f"/api/v1/studio/versions/{version_id}/evaluations",
        headers=_headers(csrf, f"start-{provider_flag}-judge"),
    )
    run_id = str(started.json()["evaluation_run_id"])
    deadline = time.monotonic() + 15
    body: dict[str, Any] = {}
    while time.monotonic() < deadline:
        body = cast(dict[str, Any], client.get(f"/api/v1/studio/evaluations/{run_id}").json())
        if body.get("state") in {"COMPLETED", "FAILED"}:
            break
        time.sleep(0.03)
    assert body["state"] == "COMPLETED"
    assert body["progress"]["errors"] == 13
    assert body["release_eligible"] is False
    resources = _resources(client)
    with resources.session_factory() as db:
        errors = list(
            db.scalars(
                select(EvaluationCaseResult).where(
                    EvaluationCaseResult.evaluation_run_id == run_id,
                    EvaluationCaseResult.state == "ERROR",
                )
            )
        )
    assert len(errors) == 13
    assert {item.safe_error_code for item in errors} == {expected_code}


def test_startup_marks_active_evaluation_failed(client: TestClient) -> None:
    resources = _resources(client)
    csrf, version_id = _ready_version(client)
    assert (
        client.post(
            f"/api/v1/studio/versions/{version_id}/submit",
            headers=_headers(csrf, "submit-for-restart"),
        ).status_code
        == 200
    )
    now = utc_now()
    with resources.session_factory() as db:
        session = db.scalar(select(DemoSession))
        assert session is not None
        run = EvaluationRun(
            id=str(uuid4()),
            version_id=version_id,
            triggered_by_session_id=session.id,
            state="QUEUED",
            suite_version="ocean-literacy-v1",
            online_model=resources.chat_provider.online_model,
            judge_model=resources.judge_provider.model,
            embedding_model=resources.embedding_provider.model,
            moderation_model=resources.chat_provider.moderation_model,
            total_cases=16,
            completed_cases=4,
            passed_cases=4,
            failed_cases=0,
            error_cases=0,
            grounded_pass_rate=None,
            age_average=None,
            instruction_average=None,
            release_eligible=0,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0,
            error_code=None,
            created_at=now,
            started_at=now,
            finished_at=None,
            timeout_at=now - timedelta(seconds=1),
        )
        db.add(run)
        db.commit()
        run_id = run.id
    process_evaluation(resources, run_id)
    with resources.session_factory() as db:
        timed_out = db.get(EvaluationRun, run_id)
        assert timed_out is not None
        assert timed_out.state == "FAILED"
        assert timed_out.error_code == "EVALUATION_TIMEOUT"
        timed_out.state = "RUNNING"
        timed_out.error_code = None
        timed_out.finished_at = None
        timed_out.timeout_at = now + timedelta(minutes=5)
        db.commit()
    run_startup_maintenance(resources)
    with resources.session_factory() as db:
        restarted = db.get(EvaluationRun, run_id)
        assert restarted is not None
        assert restarted.state == "FAILED"
        assert restarted.error_code == "SERVICE_RESTARTED"
        assert restarted.finished_at is not None


def test_evaluation_scores_have_no_mutation_endpoint(client: TestClient) -> None:
    paths = cast(dict[str, dict[str, object]], client.get("/openapi.json").json()["paths"])
    case_paths = {path: methods for path, methods in paths.items() if "evaluation-cases" in path}
    assert case_paths
    assert all(set(methods) == {"get"} for methods in case_paths.values())
