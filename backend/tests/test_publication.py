from __future__ import annotations

import time
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import utc_now
from app.db.models import (
    Agent,
    AgentVersion,
    ChatRun,
    EvaluationRun,
    Message,
    MessageCitation,
    RunNodeTrace,
)
from app.db.readiness import RuntimeResources
from app.main import create_app
from tests.conftest import FakeChatProvider
from tests.test_chat import _headers, _ready_version  # pyright: ignore[reportPrivateUsage]
from tests.test_evaluation import _teacher  # pyright: ignore[reportPrivateUsage]
from tests.test_review import _evaluate  # pyright: ignore[reportPrivateUsage]

ORIGIN = {"Origin": "http://testserver"}


def _resources(client: TestClient) -> RuntimeResources:
    return cast(RuntimeResources, cast(FastAPI, client.app).state.resources)


def _approved_version(client: TestClient) -> tuple[str, str, str]:
    csrf, version_id = _ready_version(client)
    submitted = client.post(
        f"/api/v1/studio/versions/{version_id}/submit",
        headers=_headers(csrf, "publish-submit"),
    )
    assert submitted.status_code == 200
    denied = client.post(
        f"/api/v1/studio/versions/{version_id}/publish",
        headers=_headers(csrf, "publish-too-early"),
        json={"slug": "ocean-explorer"},
    )
    assert denied.status_code == 403
    csrf = _teacher(client, csrf)
    unapproved = client.post(
        f"/api/v1/studio/versions/{version_id}/publish",
        headers=_headers(csrf, "publish-unapproved"),
        json={"slug": "ocean-explorer"},
    )
    assert unapproved.status_code == 409
    run_id = _evaluate(client, csrf, version_id, "publish-evaluate")
    resources = _resources(client)
    with resources.session_factory() as db:
        run = db.get(EvaluationRun, run_id)
        assert run is not None
        run.release_eligible = 1
        db.commit()
    approved = client.post(
        f"/api/v1/studio/versions/{version_id}/approve",
        headers=_headers(csrf),
        json={"evaluation_run_id": run_id},
    )
    assert approved.status_code == 200
    return csrf, version_id, str(approved.json()["version"]["agent_id"])


def _wait_public(client: TestClient, run_id: str, token: str) -> dict[str, Any]:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        response = client.get(
            f"/api/v1/public/runs/{run_id}",
            headers={"X-Public-Run-Token": token},
        )
        assert response.status_code == 200, response.text
        assert response.headers["Cache-Control"] == "no-store"
        body = cast(dict[str, Any], response.json())
        if body["status"] in {"COMPLETED", "FAILED"}:
            return body
        time.sleep(0.02)
    raise AssertionError("public run did not finish")


def test_publish_public_chat_privacy_rate_limit_and_withdraw(
    client: TestClient, chat_provider: FakeChatProvider
) -> None:
    csrf, version_id, agent_id = _approved_version(client)
    invalid_slug = client.post(
        f"/api/v1/studio/versions/{version_id}/publish",
        headers=_headers(csrf, "publish-invalid-slug"),
        json={"slug": "Not Valid"},
    )
    assert invalid_slug.status_code == 422
    resources = _resources(client)
    now = utc_now()
    with resources.session_factory() as db:
        db.add(
            Agent(
                id="00000000-0000-4000-8000-000000000099",
                slug="taken-address",
                display_name="Existing public address",
                current_draft_version_id=None,
                published_version_id=None,
                created_at=now,
                updated_at=now,
                deleted_at=None,
                is_fixed_sample=0,
            )
        )
        db.commit()
    conflict = client.post(
        f"/api/v1/studio/versions/{version_id}/publish",
        headers=_headers(csrf, "publish-conflict"),
        json={"slug": "taken-address"},
    )
    assert conflict.status_code == 409
    with resources.session_factory() as db:
        agent = db.get(Agent, agent_id)
        version = db.get(AgentVersion, version_id)
        assert agent is not None and agent.published_version_id is None
        assert version is not None and version.state == "APPROVED"
    published = client.post(
        f"/api/v1/studio/versions/{version_id}/publish",
        headers=_headers(csrf, "publish-approved"),
        json={"slug": "ocean-explorer"},
    )
    assert published.status_code == 200, published.text
    replay = client.post(
        f"/api/v1/studio/versions/{version_id}/publish",
        headers=_headers(csrf, "publish-approved"),
        json={"slug": "ocean-explorer"},
    )
    assert replay.json() == published.json()

    summary = client.get("/api/v1/studio/agents").json()["agents"][0]
    assert summary["slug"] == "ocean-explorer"
    assert summary["published_version"]["id"] == version_id
    assert summary["published_version"]["state"] == "PUBLISHED"

    metadata = client.get("/api/v1/public/agents/ocean-explorer")
    assert metadata.status_code == 200
    assert metadata.headers["Cache-Control"] == "public, max-age=60"
    assert set(metadata.json()) == {
        "slug",
        "project_name",
        "problem_to_solve",
        "intended_users",
        "audience_age",
        "success_goal",
        "welcome_message",
        "version_number",
        "status",
        "builder_label",
        "knowledge_source",
    }
    assert "custom_instructions" not in metadata.text

    prompt = "Public-only canary 8472: How do ocean currents affect climate?"
    chat_provider.answer_override = (
        "Public-only answer canary 5931: currents move heat and shape regional climate."
    )
    started = client.post(
        "/api/v1/public/agents/ocean-explorer/runs",
        headers={**ORIGIN, "Idempotency-Key": "public-grounded"},
        json={"message": prompt},
    )
    assert started.status_code == 202, started.text
    assert started.headers["Cache-Control"] == "no-store"
    run_id = str(started.json()["run_id"])
    token = str(started.json()["run_token"])
    isolated = client.get(
        f"/api/v1/public/runs/{run_id}",
        headers={"X-Public-Run-Token": "wrong-public-run-token"},
    )
    assert isolated.status_code == 404
    completed = _wait_public(client, run_id, token)
    assert completed["result"]["type"] == "ANSWERED"
    assert completed["result"]["citations"]
    assert "usage" not in completed and "models" not in completed and "trace" not in completed

    answer = str(completed["result"]["answer"])
    with resources.session_factory() as db:
        public_run = db.get(ChatRun, run_id)
        assert public_run is not None and public_run.surface == "PUBLIC"
        assert public_run.input_message_id is None and public_run.output_message_id is None
        assert (
            db.scalar(
                select(func.count()).select_from(RunNodeTrace).where(RunNodeTrace.run_id == run_id)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(MessageCitation)
                .join(Message, Message.id == MessageCitation.message_id)
                .where(Message.run_id == run_id)
            )
            == 0
        )
        assert db.scalar(select(Message).where(Message.content.in_([prompt, answer]))) is None
    assert prompt.encode() not in resources.settings.database_path.read_bytes()
    assert answer.encode() not in resources.settings.database_path.read_bytes()

    calls_before = len(chat_provider.calls)
    pii_text = "My email is public-canary-91@example.test"
    blocked_start = client.post(
        "/api/v1/public/agents/ocean-explorer/runs",
        headers={**ORIGIN, "Idempotency-Key": "public-pii-block"},
        json={"message": pii_text},
    )
    blocked = _wait_public(
        client,
        str(blocked_start.json()["run_id"]),
        str(blocked_start.json()["run_token"]),
    )
    assert blocked["result"]["type"] == "BLOCKED"
    assert len(chat_provider.calls) == calls_before
    assert pii_text.encode() not in resources.settings.database_path.read_bytes()

    resources.settings.public_hourly_limit = 2
    restarted_app = create_app(
        resources.settings,
        embedding_provider=resources.embedding_provider,
        chat_provider=resources.chat_provider,
        judge_provider=resources.judge_provider,
    )
    with TestClient(restarted_app) as restarted:
        limited = restarted.post(
            "/api/v1/public/agents/ocean-explorer/runs",
            headers={**ORIGIN, "Idempotency-Key": "public-over-limit"},
            json={"message": "What is ocean literacy?"},
        )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "PUBLIC_RATE_LIMITED"
    studio = client.post(
        f"/api/v1/studio/versions/{version_id}/runs",
        headers=_headers(csrf, "studio-after-public-limit"),
        json={"message": "How do ocean currents affect climate?"},
    )
    assert studio.status_code == 202

    with resources.session_factory() as db:
        public_run = db.get(ChatRun, run_id)
        assert public_run is not None
        public_run.expires_at = now
        db.commit()
    assert (
        client.get(
            f"/api/v1/public/runs/{run_id}",
            headers={"X-Public-Run-Token": token},
        ).status_code
        == 404
    )

    withdrawn = client.post(
        f"/api/v1/studio/versions/{version_id}/withdraw",
        headers=_headers(csrf, "withdraw-public"),
    )
    assert withdrawn.status_code == 200
    withdraw_replay = client.post(
        f"/api/v1/studio/versions/{version_id}/withdraw",
        headers=_headers(csrf, "withdraw-public"),
    )
    assert withdraw_replay.json() == withdrawn.json()
    assert client.get("/api/v1/public/agents/ocean-explorer").status_code == 404


def test_admin_reset_preserves_explicit_fixed_sample(client: TestClient) -> None:
    csrf, version_id, agent_id = _approved_version(client)
    published = client.post(
        f"/api/v1/studio/versions/{version_id}/publish",
        headers=_headers(csrf, "publish-fixed"),
        json={"slug": "ocean-explorer"},
    )
    assert published.status_code == 200
    token_header = {"X-Admin-Reset-Token": "test-admin-token-value"}
    seeded = client.post(f"/api/v1/admin/seed-fixed-sample/{agent_id}", headers=token_header)
    assert seeded.status_code == 200

    # Create an ordinary temporary Agent after returning to Student mode.
    changed = client.patch(
        "/api/v1/studio/session/role", headers=_headers(csrf), json={"role": "STUDENT"}
    )
    student_csrf = str(changed.json()["csrf_token"])
    temporary = client.post(
        "/api/v1/studio/agents",
        headers=_headers(student_csrf, "temporary-reset-agent"),
        json={
            "template": "KNOWLEDGE_EXPLORER",
            "project_name": "Temporary Explorer",
            "problem_to_solve": "Test that temporary workspace data is removed safely.",
            "intended_users": "Interview demo reviewers",
            "audience_age": "AGE_12_17",
            "success_goal": "Confirm fixed sample reset behavior is deterministic.",
            "welcome_message": "This temporary Agent should be deleted.",
            "tone": "CURIOUS",
            "response_length": "SHORT",
            "custom_instructions": "",
        },
    )
    assert temporary.status_code == 201
    temporary_id = str(temporary.json()["agent"]["id"])
    denied = client.post(
        "/api/v1/admin/reset-demo-workspace",
        headers={"X-Admin-Reset-Token": "wrong", "Idempotency-Key": "reset-workspace"},
    )
    assert denied.status_code == 403
    reset_headers = {**token_header, "Idempotency-Key": "reset-workspace"}
    reset = client.post("/api/v1/admin/reset-demo-workspace", headers=reset_headers)
    assert reset.status_code == 200, reset.text
    assert reset.json()["deleted_agents"] == 1
    assert reset.json()["preserved_fixed_samples"] == 1
    assert (
        client.post("/api/v1/admin/reset-demo-workspace", headers=reset_headers).json()
        == reset.json()
    )
    assert client.get("/api/v1/public/agents/ocean-explorer").status_code == 200
    resources = _resources(client)
    with resources.session_factory() as db:
        assert db.get(Agent, agent_id) is not None
        assert db.get(Agent, temporary_id) is None
        assert db.get(AgentVersion, version_id) is not None
