from __future__ import annotations

import asyncio
from typing import Annotated, cast

from fastapi import APIRouter, File, Header, Request, UploadFile, status
from fastapi.responses import Response

from app.api.dependencies import (
    CurrentSession,
    DatabaseSession,
    MutationSession,
    RuntimeResource,
)
from app.api.errors import ApiError
from app.api.schemas import IngestionJobView, KnowledgeUploadResponse
from app.db.readiness import RuntimeResources
from app.services.knowledge import (
    MAX_UPLOAD_BYTES,
    create_upload,
    delete_document,
    get_job,
    process_ingestion_job,
    retry_job,
)

router = APIRouter(prefix="/studio", tags=["studio-knowledge"])


def _schedule(request: Request, resources: RuntimeResources, job_id: str) -> None:
    job_ids = cast(set[str], request.app.state.ingestion_job_ids)
    if job_id in job_ids:
        return
    job_ids.add(job_id)
    task = asyncio.create_task(asyncio.to_thread(process_ingestion_job, resources, job_id))
    tasks = cast(set[asyncio.Task[None]], request.app.state.ingestion_tasks)
    tasks.add(task)

    def complete(completed: asyncio.Task[None]) -> None:
        tasks.discard(completed)
        job_ids.discard(job_id)

    task.add_done_callback(complete)


@router.post(
    "/versions/{version_id}/knowledge",
    response_model=KnowledgeUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_knowledge(
    request: Request,
    version_id: str,
    db: DatabaseSession,
    resources: RuntimeResource,
    session: MutationSession,
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> KnowledgeUploadResponse:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "FILE_TOO_LARGE", "Files must be 15 MB or smaller.")
    response = create_upload(
        db,
        resources,
        session,
        version_id,
        file.filename,
        file.content_type,
        content,
        idempotency_key,
    )
    if get_job(db, response.job_id).state.value == "UPLOADED":
        _schedule(request, resources, response.job_id)
    return response


@router.get("/ingestion-jobs/{job_id}", response_model=IngestionJobView)
def read_ingestion_job(
    job_id: str,
    db: DatabaseSession,
    _session: CurrentSession,
) -> IngestionJobView:
    return get_job(db, job_id)


@router.post(
    "/ingestion-jobs/{job_id}/retry",
    response_model=KnowledgeUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_ingestion_job(
    request: Request,
    job_id: str,
    db: DatabaseSession,
    resources: RuntimeResource,
    session: MutationSession,
) -> KnowledgeUploadResponse:
    response = retry_job(db, resources, session, job_id)
    _schedule(request, resources, response.job_id)
    return response


@router.delete(
    "/versions/{version_id}/knowledge/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_knowledge(
    version_id: str,
    document_id: str,
    db: DatabaseSession,
    resources: RuntimeResource,
    session: MutationSession,
) -> Response:
    delete_document(db, resources, session, version_id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
