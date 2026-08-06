from __future__ import annotations

import time
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    AgentVersion,
    EvaluationRun,
    IngestionJob,
    KnowledgeDocument,
    TeacherReview,
)
from app.db.readiness import RuntimeResources
from tests.conftest import FakeEmbeddingProvider
from tests.test_chat import _headers, _ready_version  # pyright: ignore[reportPrivateUsage]
from tests.test_evaluation import _teacher  # pyright: ignore[reportPrivateUsage]


def _resources(client: TestClient) -> RuntimeResources:
    return cast(RuntimeResources, cast(FastAPI, client.app).state.resources)


def _student(client: TestClient, csrf: str) -> str:
    response = client.patch(
        "/api/v1/studio/session/role",
        headers=_headers(csrf),
        json={"role": "STUDENT"},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def _evaluate(client: TestClient, csrf: str, version_id: str, key: str) -> str:
    started = client.post(
        f"/api/v1/studio/versions/{version_id}/evaluations",
        headers=_headers(csrf, key),
    )
    assert started.status_code == 202, started.text
    run_id = str(started.json()["evaluation_run_id"])
    deadline = time.monotonic() + 15
    body: dict[str, Any] = {}
    while time.monotonic() < deadline:
        body = cast(dict[str, Any], client.get(f"/api/v1/studio/evaluations/{run_id}").json())
        if body.get("state") in {"COMPLETED", "FAILED"}:
            break
        time.sleep(0.03)
    assert body.get("state") == "COMPLETED", body
    return run_id


def test_request_changes_next_version_compare_and_approve(
    client: TestClient, embedding_provider: FakeEmbeddingProvider
) -> None:
    csrf, v1_id = _ready_version(client)
    resources = _resources(client)
    submitted = client.post(
        f"/api/v1/studio/versions/{v1_id}/submit",
        headers=_headers(csrf, "review-submit-v1"),
    )
    assert submitted.status_code == 200
    csrf = _teacher(client, csrf)
    v1_run = _evaluate(client, csrf, v1_id, "review-evaluate-v1")

    missing_feedback = client.post(
        f"/api/v1/studio/versions/{v1_id}/request-changes",
        headers=_headers(csrf),
        json={"evaluation_run_id": v1_run, "feedback": ""},
    )
    assert missing_feedback.status_code == 422
    requested = client.post(
        f"/api/v1/studio/versions/{v1_id}/request-changes",
        headers=_headers(csrf),
        json={
            "evaluation_run_id": v1_run,
            "feedback": "Make the younger explanation use evidence from the expected page.",
        },
    )
    assert requested.status_code == 200, requested.text
    assert requested.json()["version"]["state"] == "CHANGES_REQUESTED"
    assert requested.json()["review"]["decision"] == "REQUEST_CHANGES"

    csrf = _student(client, csrf)
    immutable = client.patch(
        f"/api/v1/studio/versions/{v1_id}",
        headers=_headers(csrf),
        json={"tone": "FRIENDLY"},
    )
    assert immutable.status_code == 409
    invalid_reflection = client.post(
        f"/api/v1/studio/versions/{v1_id}/next-version",
        headers=_headers(csrf, "review-invalid-reflection"),
        json={"what_changed": "", "why_changed": ""},
    )
    assert invalid_reflection.status_code == 422

    embedding_calls = len(embedding_provider.calls)
    next_version = client.post(
        f"/api/v1/studio/versions/{v1_id}/next-version",
        headers=_headers(csrf, "review-create-v2"),
        json={
            "what_changed": "Made the younger explanation more evidence-led.",
            "why_changed": "The Teacher found weak expected-page overlap.",
        },
    )
    assert next_version.status_code == 201, next_version.text
    v2 = next_version.json()
    v2_id = str(v2["id"])
    assert v2["version_number"] == 2
    assert v2["source_version_id"] == v1_id
    assert v2["knowledge_status"] == "READY"
    assert v2["active_document_id"] != submitted.json()["active_document_id"]
    assert len(embedding_provider.calls) == embedding_calls
    replay = client.post(
        f"/api/v1/studio/versions/{v1_id}/next-version",
        headers=_headers(csrf, "review-create-v2"),
        json={
            "what_changed": "Made the younger explanation more evidence-led.",
            "why_changed": "The Teacher found weak expected-page overlap.",
        },
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == v2_id
    with resources.session_factory() as db:
        documents = list(
            db.scalars(
                select(KnowledgeDocument).where(KnowledgeDocument.version_id.in_([v1_id, v2_id]))
            )
        )
        ingestion_jobs = list(db.scalars(select(IngestionJob)))
    assert len(documents) == 2
    assert len(ingestion_jobs) == 1
    collection = resources.chroma.get_collection("knowledge_chunks")
    assert collection.get(where={"version_id": v1_id})["ids"]
    assert collection.get(where={"version_id": v2_id})["ids"]

    edited = client.patch(
        f"/api/v1/studio/versions/{v2_id}",
        headers=_headers(csrf),
        json={"tone": "FRIENDLY"},
    )
    assert edited.status_code == 200
    assert (
        client.post(
            f"/api/v1/studio/versions/{v2_id}/submit",
            headers=_headers(csrf, "review-submit-v2"),
        ).status_code
        == 200
    )
    csrf = _teacher(client, csrf)
    v2_run = _evaluate(client, csrf, v2_id, "review-evaluate-v2")

    comparison = client.get(
        f"/api/v1/studio/versions/{v1_id}/compare/{v2_id}",
        params={"left_run_id": v1_run, "right_run_id": v2_run},
    )
    assert comparison.status_code == 200, comparison.text
    assert len(comparison.json()["cases"]) == 16
    assert len(comparison.json()["categories"]) == 6
    wrong_approval = client.post(
        f"/api/v1/studio/versions/{v2_id}/approve",
        headers=_headers(csrf),
        json={"evaluation_run_id": v1_run},
    )
    assert wrong_approval.status_code == 409
    with resources.session_factory() as db:
        run = db.get(EvaluationRun, v2_run)
        assert run is not None
        run.release_eligible = 1
        db.commit()
    approved = client.post(
        f"/api/v1/studio/versions/{v2_id}/approve",
        headers=_headers(csrf),
        json={"evaluation_run_id": v2_run},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["version"]["state"] == "APPROVED"
    with resources.session_factory() as db:
        v1 = db.get(AgentVersion, v1_id)
        reviews = list(db.scalars(select(TeacherReview).order_by(TeacherReview.created_at)))
    assert v1 is not None and v1.state == "CHANGES_REQUESTED"
    assert [review.decision for review in reviews] == ["REQUEST_CHANGES", "APPROVE"]


def test_compare_rejects_mismatched_model_baseline(client: TestClient) -> None:
    csrf, v1_id = _ready_version(client)
    assert (
        client.post(
            f"/api/v1/studio/versions/{v1_id}/submit",
            headers=_headers(csrf, "mismatch-submit-v1"),
        ).status_code
        == 200
    )
    csrf = _teacher(client, csrf)
    v1_run = _evaluate(client, csrf, v1_id, "mismatch-evaluate-v1")
    requested = client.post(
        f"/api/v1/studio/versions/{v1_id}/request-changes",
        headers=_headers(csrf),
        json={"evaluation_run_id": v1_run, "feedback": "Create another evidence-led version."},
    )
    assert requested.status_code == 200
    csrf = _student(client, csrf)
    created = client.post(
        f"/api/v1/studio/versions/{v1_id}/next-version",
        headers=_headers(csrf, "mismatch-create-v2"),
        json={"what_changed": "Changed the tone.", "why_changed": "Test comparison."},
    )
    v2_id = str(created.json()["id"])
    assert (
        client.post(
            f"/api/v1/studio/versions/{v2_id}/submit",
            headers=_headers(csrf, "mismatch-submit-v2"),
        ).status_code
        == 200
    )
    csrf = _teacher(client, csrf)
    v2_run = _evaluate(client, csrf, v2_id, "mismatch-evaluate-v2")
    resources = _resources(client)
    with resources.session_factory() as db:
        run = db.get(EvaluationRun, v2_run)
        assert run is not None
        run.judge_model = "different-baseline"
        db.commit()
    mismatch = client.get(
        f"/api/v1/studio/versions/{v1_id}/compare/{v2_id}",
        params={"left_run_id": v1_run, "right_run_id": v2_run},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "COMPARISON_BASELINE_MISMATCH"
