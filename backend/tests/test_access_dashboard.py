from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import utc_now
from app.db.models import Agent, AgentVersion, AuditEvent, DemoSession, IdempotencyRecord
from app.db.readiness import RuntimeResources

ORIGIN = {"Origin": "http://testserver"}


def access(client: TestClient) -> str:
    response = client.post(
        "/api/v1/studio/access",
        json={"access_code": "test-access"},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def headers(csrf: str, **extra: str) -> dict[str, str]:
    return {**ORIGIN, "X-CSRF-Token": csrf, **extra}


def runtime_resources(client: TestClient) -> RuntimeResources:
    application = cast(FastAPI, client.app)
    return cast(RuntimeResources, application.state.resources)


def agent_payload(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "template": "KNOWLEDGE_EXPLORER",
        "project_name": "Ocean Explorer",
        "problem_to_solve": "Help learners understand the ocean using trusted evidence.",
        "intended_users": "Students learning ocean science",
        "audience_age": "AGE_12_17",
        "success_goal": "Answer ocean questions clearly with evidence from the source.",
        "welcome_message": "What would you like to discover about the ocean?",
        "tone": "CURIOUS",
        "response_length": "BALANCED",
        "custom_instructions": "Ask one useful follow-up question when needed.",
    }
    payload.update(changes)
    return payload


def test_access_cookie_failure_rate_limit_and_origin(client: TestClient) -> None:
    missing_origin = client.post("/api/v1/studio/access", json={"access_code": "test-access"})
    assert missing_origin.status_code == 403

    for _ in range(5):
        denied = client.post(
            "/api/v1/studio/access",
            json={"access_code": "incorrect-code"},
            headers=ORIGIN,
        )
        assert denied.status_code == 401
        assert denied.json()["error"]["code"] == "ACCESS_DENIED"
        assert "incorrect-code" not in denied.text

    limited = client.post(
        "/api/v1/studio/access",
        json={"access_code": "test-access"},
        headers=ORIGIN,
    )
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]
    assert limited.json()["error"]["code"] == "ACCESS_RATE_LIMITED"


def test_session_restore_rotates_csrf_role_and_sign_out(client: TestClient) -> None:
    csrf = access(client)
    cookie = client.cookies.get("agentsprout_session")
    assert cookie

    restored = client.get("/api/v1/studio/session")
    assert restored.status_code == 200
    rotated = str(restored.json()["csrf_token"])
    assert rotated != csrf

    old_token = client.patch(
        "/api/v1/studio/session/role",
        json={"role": "TEACHER"},
        headers=headers(csrf),
    )
    assert old_token.status_code == 400
    assert old_token.json()["error"]["code"] == "CSRF_INVALID"

    changed = client.patch(
        "/api/v1/studio/session/role",
        json={"role": "TEACHER"},
        headers=headers(rotated),
    )
    assert changed.status_code == 200
    assert changed.json()["session"]["role"] == "TEACHER"
    latest_csrf = str(changed.json()["csrf_token"])

    signed_out = client.delete("/api/v1/studio/session", headers=headers(latest_csrf))
    assert signed_out.status_code == 204
    assert client.get("/api/v1/studio/session").status_code == 401


def test_access_sets_an_opaque_http_only_cookie(client: TestClient) -> None:
    response = client.post(
        "/api/v1/studio/access",
        json={"access_code": "test-access"},
        headers=ORIGIN,
    )
    cookie = response.headers["set-cookie"]
    assert "agentsprout_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "test-access" not in cookie
    assert "test-access" not in response.text

    resources = runtime_resources(client)
    with resources.session_factory() as db:
        session = db.scalar(select(DemoSession))
        assert session is not None
        assert len(session.token_hash) == len(session.csrf_hash) == 64
        assert client.cookies.get("agentsprout_session") != session.token_hash


def test_expired_session_is_rejected(client: TestClient) -> None:
    access(client)
    resources = runtime_resources(client)
    with resources.session_factory() as db:
        session = db.scalar(select(DemoSession))
        assert session is not None
        session.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()

    response = client.get("/api/v1/studio/session")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


def test_agent_create_is_idempotent_persistent_and_audited(client: TestClient) -> None:
    csrf = access(client)
    request_headers = headers(csrf, **{"Idempotency-Key": "create-ocean-explorer"})

    created = client.post("/api/v1/studio/agents", json=agent_payload(), headers=request_headers)
    replay = client.post("/api/v1/studio/agents", json=agent_payload(), headers=request_headers)

    assert created.status_code == replay.status_code == 201
    assert created.json() == replay.json()
    agent_id = created.json()["agent"]["id"]
    version_id = created.json()["version"]["id"]

    listing = client.get("/api/v1/studio/agents")
    aggregate = client.get(f"/api/v1/studio/agents/{agent_id}")
    version = client.get(f"/api/v1/studio/versions/{version_id}")
    assert listing.json()["agents"][0]["display_name"] == "Ocean Explorer"
    assert aggregate.json()["current_draft_version_id"] == version_id
    assert version.json()["state"] == "DRAFT"

    resources = runtime_resources(client)
    with resources.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Agent)) == 1
        assert db.scalar(select(func.count()).select_from(AgentVersion)) == 1
        assert db.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1
        audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "AGENT_CREATED"))
        assert audit is not None
        assert "test-access" not in audit.result


def test_agent_create_conflict_validation_and_security(client: TestClient) -> None:
    csrf = access(client)
    request_headers = headers(csrf, **{"Idempotency-Key": "same-request-key"})
    assert (
        client.post(
            "/api/v1/studio/agents", json=agent_payload(), headers=request_headers
        ).status_code
        == 201
    )

    conflict = client.post(
        "/api/v1/studio/agents",
        json=agent_payload(project_name="Different Explorer"),
        headers=request_headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    missing_csrf = client.post(
        "/api/v1/studio/agents",
        json=agent_payload(),
        headers={**ORIGIN, "Idempotency-Key": "another-request-key"},
    )
    assert missing_csrf.status_code == 400

    wrong_origin = client.post(
        "/api/v1/studio/agents",
        json=agent_payload(),
        headers={
            "Origin": "https://attacker.example",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "third-request-key",
        },
    )
    assert wrong_origin.status_code == 403

    invalid = client.post(
        "/api/v1/studio/agents",
        json=agent_payload(problem_to_solve="short", protected_field="forged"),
        headers=headers(csrf, **{"Idempotency-Key": "invalid-request-key"}),
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_student_can_edit_text_safely_but_teacher_cannot_mutate(client: TestClient) -> None:
    csrf = access(client)
    created = client.post(
        "/api/v1/studio/agents",
        json=agent_payload(),
        headers=headers(csrf, **{"Idempotency-Key": "editable-agent-key"}),
    )
    version_id = created.json()["version"]["id"]

    script_text = '<script>alert("not executed")</script> Ocean notes'
    edited = client.patch(
        f"/api/v1/studio/versions/{version_id}",
        json={"custom_instructions": script_text, "project_name": "Ocean Field Guide"},
        headers=headers(csrf),
    )
    assert edited.status_code == 200
    assert edited.json()["custom_instructions"] == script_text

    protected = client.patch(
        f"/api/v1/studio/versions/{version_id}",
        json={"state": "PUBLISHED"},
        headers=headers(csrf),
    )
    assert protected.status_code == 422

    null_field = client.patch(
        f"/api/v1/studio/versions/{version_id}",
        json={"project_name": None},
        headers=headers(csrf),
    )
    assert null_field.status_code == 422

    role_change = client.patch(
        "/api/v1/studio/session/role",
        json={"role": "TEACHER"},
        headers=headers(csrf),
    )
    teacher_csrf = str(role_change.json()["csrf_token"])
    denied_create = client.post(
        "/api/v1/studio/agents",
        json=agent_payload(),
        headers=headers(teacher_csrf, **{"Idempotency-Key": "teacher-create-key"}),
    )
    denied_edit = client.patch(
        f"/api/v1/studio/versions/{version_id}",
        json={"project_name": "Forged edit"},
        headers=headers(teacher_csrf),
    )
    assert denied_create.status_code == denied_edit.status_code == 403
    assert client.get(f"/api/v1/studio/versions/{version_id}").status_code == 200
