from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import select

from app.core.security import utc_now
from app.core.startup import run_startup_maintenance
from app.db.models import AgentVersion, IngestionJob, KnowledgeDocument
from app.db.readiness import RuntimeResources
from app.domain.enums import DocumentStatus, IngestionState
from app.services.knowledge import chunk_pages, retrieve
from tests.conftest import FakeEmbeddingProvider

ORIGIN = {"Origin": "http://testserver"}


def _access(client: TestClient) -> str:
    response = client.post(
        "/api/v1/studio/access",
        json={"access_code": "test-access"},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def _headers(csrf: str, key: str | None = None) -> dict[str, str]:
    result = {**ORIGIN, "X-CSRF-Token": csrf}
    if key:
        result["Idempotency-Key"] = key
    return result


def _create_version(client: TestClient, csrf: str) -> str:
    response = client.post(
        "/api/v1/studio/agents",
        headers=_headers(csrf, "knowledge-agent-key"),
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
    assert response.status_code == 201
    return str(response.json()["version"]["id"])


def _resources(client: TestClient) -> RuntimeResources:
    application = cast(FastAPI, client.app)
    return cast(RuntimeResources, application.state.resources)


def _wait(client: TestClient, job_id: str, terminal: str = "READY") -> dict[str, Any]:
    deadline = time.monotonic() + 8
    observed: set[str] = set()
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/studio/ingestion-jobs/{job_id}")
        assert response.status_code == 200
        body = cast(dict[str, Any], response.json())
        observed.add(str(body["state"]))
        if body["state"] in {"READY", "FAILED"}:
            assert body["state"] == terminal, observed
            return body
        time.sleep(0.03)
    raise AssertionError(f"job did not finish; observed={observed}")


def _upload(
    client: TestClient,
    csrf: str,
    version_id: str,
    name: str,
    content: bytes,
    media_type: str,
    key: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/studio/versions/{version_id}/knowledge",
        headers=_headers(csrf, key),
        files={"file": (name, content, media_type)},
    )
    assert response.status_code == 202, response.text
    return cast(dict[str, Any], response.json())


def _pdf_with_text(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, item in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + item + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)


def test_txt_upload_ready_persists_and_retrieves_exact_document(
    client: TestClient, embedding_provider: FakeEmbeddingProvider
) -> None:
    csrf = _access(client)
    version_id = _create_version(client, csrf)
    text = (
        "Ocean currents redistribute heat and strongly influence climate and regional "
        "temperature patterns.\n\nCoral reefs support diverse ocean ecosystems. "
    ) * 12
    uploaded = _upload(
        client,
        csrf,
        version_id,
        "ocean-notes.txt",
        text.encode(),
        "text/plain",
        "upload-ocean-notes",
    )
    _wait(client, str(uploaded["job_id"]))

    version = client.get(f"/api/v1/studio/versions/{version_id}").json()
    assert version["knowledge_status"] == "READY"
    assert version["knowledge"]["active_document"]["chunk_count"] > 1
    assert version["knowledge"]["latest_job"]["state"] == "READY"

    resources = _resources(client)
    results = retrieve(resources, version_id, "How do ocean currents affect climate?")
    assert results
    assert all(item.filename == "ocean-notes.txt" for item in results)
    assert all(item.page_number == 1 for item in results)
    collection = resources.chroma.get_collection("knowledge_chunks")
    assert collection.count() == version["knowledge"]["active_document"]["chunk_count"]

    calls_before_replay = len(embedding_provider.calls)
    replay = client.post(
        f"/api/v1/studio/versions/{version_id}/knowledge",
        headers=_headers(csrf, "upload-ocean-notes"),
        files={"file": ("ocean-notes.txt", text.encode(), "text/plain")},
    )
    assert replay.status_code == 202
    assert replay.json() == uploaded
    time.sleep(0.05)
    assert len(embedding_provider.calls) == calls_before_replay

    duplicate = client.post(
        f"/api/v1/studio/versions/{version_id}/knowledge",
        headers=_headers(csrf, "second-upload-key"),
        files={"file": ("ocean-notes.txt", text.encode(), "text/plain")},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_DOCUMENT"


def test_valid_text_pdf_and_scanned_pdf_rejection(client: TestClient) -> None:
    csrf = _access(client)
    version_id = _create_version(client, csrf)
    pdf = _pdf_with_text("Ocean climate currents and temperature evidence. " * 10)
    uploaded = _upload(
        client,
        csrf,
        version_id,
        "source.pdf",
        pdf,
        "application/pdf",
        "valid-pdf-upload",
    )
    _wait(client, str(uploaded["job_id"]))

    scanned = (
        b"%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Count 0 /Kids [] >>endobj\n"
        b"trailer<< /Root 1 0 R >>\n%%EOF"
    )
    failed = _upload(
        client,
        csrf,
        version_id,
        "scan.pdf",
        scanned,
        "application/pdf",
        "scanned-pdf-upload",
    )
    outcome = _wait(client, str(failed["job_id"]), "FAILED")
    assert outcome["error_code"] in {"PDF_SCANNED_OR_EMPTY", "PDF_PARSE_FAILED"}
    assert outcome["retryable"] is False
    version = client.get(f"/api/v1/studio/versions/{version_id}").json()
    assert version["knowledge"]["active_document"]["original_filename"] == "source.pdf"


def test_provider_failure_preserves_previous_document_then_retry_replaces_it(
    client: TestClient, embedding_provider: FakeEmbeddingProvider
) -> None:
    csrf = _access(client)
    version_id = _create_version(client, csrf)
    first = _upload(
        client,
        csrf,
        version_id,
        "first.md",
        ("Ocean currents influence climate. " * 40).encode(),
        "text/markdown",
        "first-doc-upload",
    )
    _wait(client, str(first["job_id"]))

    embedding_provider.fail_next = True
    second = _upload(
        client,
        csrf,
        version_id,
        "replacement.md",
        ("Coral reefs support ocean life. " * 40).encode(),
        "text/markdown",
        "replacement-upload",
    )
    failed = _wait(client, str(second["job_id"]), "FAILED")
    assert failed["error_code"] == "EMBEDDING_PROVIDER_FAILED"
    assert failed["retryable"] is True
    during_failure = client.get(f"/api/v1/studio/versions/{version_id}").json()
    assert during_failure["knowledge_status"] == "FAILED"
    assert during_failure["knowledge"]["active_document"]["id"] == first["document_id"]

    retried = client.post(
        f"/api/v1/studio/ingestion-jobs/{second['job_id']}/retry",
        headers=_headers(csrf),
    )
    assert retried.status_code == 202
    _wait(client, str(retried.json()["job_id"]))
    completed = client.get(f"/api/v1/studio/versions/{version_id}").json()
    assert completed["knowledge"]["active_document"]["id"] == second["document_id"]

    resources = _resources(client)
    old_vectors = resources.chroma.get_collection("knowledge_chunks").get(
        where={"document_id": first["document_id"]}
    )
    assert old_vectors["ids"] == []


def test_restart_recovery_chunk_stability_and_upload_validation(client: TestClient) -> None:
    csrf = _access(client)
    version_id = _create_version(client, csrf)
    bad_type = client.post(
        f"/api/v1/studio/versions/{version_id}/knowledge",
        headers=_headers(csrf, "bad-type-upload"),
        files={"file": ("notes.txt", b"some content", "application/pdf")},
    )
    unsafe_name = client.post(
        f"/api/v1/studio/versions/{version_id}/knowledge",
        headers=_headers(csrf, "unsafe-name-upload"),
        files={"file": ("../notes.txt", b"some content", "text/plain")},
    )
    assert bad_type.status_code == 415
    assert unsafe_name.status_code == 422

    chunks_a = chunk_pages("a" * 64, [(3, "Ocean climate evidence. " * 100)])
    chunks_b = chunk_pages("a" * 64, [(3, "Ocean climate evidence. " * 100)])
    assert [item.id for item in chunks_a] == [item.id for item in chunks_b]
    assert all(item.page_number == 3 for item in chunks_a)

    resources = _resources(client)
    now = utc_now()
    with resources.session_factory() as db:
        version = db.get(AgentVersion, version_id)
        assert version is not None
        document = KnowledgeDocument(
            id="restart-document",
            version_id=version.id,
            original_filename="restart.txt",
            media_type="text/plain",
            extension="txt",
            byte_size=10,
            sha256="b" * 64,
            storage_path=str(Path(resources.settings.uploads_path) / "restart" / "source.txt"),
            status=DocumentStatus.EMBEDDING.value,
            page_count=1,
            chunk_count=None,
            embedding_model="text-embedding-3-small",
            error_code=None,
            is_active=0,
            created_at=now,
            ready_at=None,
            retired_at=None,
        )
        job = IngestionJob(
            id="restart-job",
            document_id=document.id,
            state=IngestionState.EMBEDDING.value,
            attempt=1,
            progress_completed=1,
            progress_total=2,
            started_at=now,
            heartbeat_at=now,
            finished_at=None,
            error_code=None,
            safe_error_message=None,
            created_at=now,
            updated_at=now,
        )
        db.add(document)
        db.flush()
        db.add(job)
        db.commit()
    run_startup_maintenance(resources)
    with resources.session_factory() as db:
        recovered = db.scalar(select(IngestionJob).where(IngestionJob.id == "restart-job"))
        assert recovered is not None
        assert recovered.state == "FAILED"
        assert recovered.error_code == "SERVICE_RESTARTED"


def test_upload_limits_encryption_page_limit_authorization_and_delete(client: TestClient) -> None:
    csrf = _access(client)
    version_id = _create_version(client, csrf)

    empty = client.post(
        f"/api/v1/studio/versions/{version_id}/knowledge",
        headers=_headers(csrf, "empty-file-upload"),
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    oversized = client.post(
        f"/api/v1/studio/versions/{version_id}/knowledge",
        headers=_headers(csrf, "oversized-upload"),
        files={"file": ("large.txt", b"x" * (15 * 1024 * 1024 + 1), "text/plain")},
    )
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "EMPTY_FILE"
    assert oversized.status_code == 413

    encrypted_writer = PdfWriter()
    encrypted_writer.add_blank_page(width=612, height=792)
    encrypted_writer.encrypt("secret")
    encrypted_buffer = BytesIO()
    encrypted_writer.write(encrypted_buffer)
    encrypted = _upload(
        client,
        csrf,
        version_id,
        "encrypted.pdf",
        encrypted_buffer.getvalue(),
        "application/pdf",
        "encrypted-upload",
    )
    encrypted_result = _wait(client, str(encrypted["job_id"]), "FAILED")
    assert encrypted_result["error_code"] == "PDF_ENCRYPTED"
    retry_denied = client.post(
        f"/api/v1/studio/ingestion-jobs/{encrypted['job_id']}/retry",
        headers=_headers(csrf),
    )
    assert retry_denied.status_code == 409

    page_writer = PdfWriter()
    for _ in range(101):
        page_writer.add_blank_page(width=612, height=792)
    page_buffer = BytesIO()
    page_writer.write(page_buffer)
    over_pages = _upload(
        client,
        csrf,
        version_id,
        "too-many-pages.pdf",
        page_buffer.getvalue(),
        "application/pdf",
        "page-limit-upload",
    )
    page_result = _wait(client, str(over_pages["job_id"]), "FAILED")
    assert page_result["error_code"] == "PDF_PAGE_LIMIT"

    role = client.patch(
        "/api/v1/studio/session/role",
        headers=_headers(csrf),
        json={"role": "TEACHER"},
    )
    teacher_csrf = str(role.json()["csrf_token"])
    denied = client.post(
        f"/api/v1/studio/versions/{version_id}/knowledge",
        headers=_headers(teacher_csrf, "teacher-upload-key"),
        files={"file": ("notes.txt", b"Ocean evidence", "text/plain")},
    )
    assert denied.status_code == 403


def test_partial_embedding_failure_cleans_staged_vectors_and_ready_delete(
    client: TestClient, embedding_provider: FakeEmbeddingProvider
) -> None:
    csrf = _access(client)
    version_id = _create_version(client, csrf)
    first = _upload(
        client,
        csrf,
        version_id,
        "baseline.txt",
        ("Ocean climate evidence. " * 40).encode(),
        "text/plain",
        "baseline-upload",
    )
    _wait(client, str(first["job_id"]))

    embedding_provider.fail_on_call = len(embedding_provider.calls) + 2
    replacement_text = "\n\n".join(
        f"Ocean coral climate evidence section {index}. " * 18 for index in range(45)
    )
    replacement = _upload(
        client,
        csrf,
        version_id,
        "large-replacement.txt",
        replacement_text.encode(),
        "text/plain",
        "partial-failure-upload",
    )
    failed = _wait(client, str(replacement["job_id"]), "FAILED")
    assert failed["error_code"] == "EMBEDDING_PROVIDER_FAILED"
    resources = _resources(client)
    collection = resources.chroma.get_collection("knowledge_chunks")
    assert collection.get(where={"document_id": replacement["document_id"]})["ids"] == []
    assert collection.get(where={"document_id": first["document_id"]})["ids"]

    removed = client.delete(
        f"/api/v1/studio/versions/{version_id}/knowledge/{replacement['document_id']}",
        headers=_headers(csrf),
    )
    assert removed.status_code == 204
    active_removed = client.delete(
        f"/api/v1/studio/versions/{version_id}/knowledge/{first['document_id']}",
        headers=_headers(csrf),
    )
    assert active_removed.status_code == 204
    version = client.get(f"/api/v1/studio/versions/{version_id}").json()
    assert version["knowledge_status"] == "NOT_ADDED"
    assert collection.get(where={"document_id": first["document_id"]})["ids"] == []
