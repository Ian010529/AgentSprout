from __future__ import annotations

import hashlib
import math
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.api.schemas import (
    IngestionJobView,
    JobProgress,
    KnowledgeDocumentView,
    KnowledgeStatus,
    KnowledgeUploadResponse,
    KnowledgeView,
)
from app.core.config import Settings
from app.core.security import as_utc, canonical_hash, keyed_hash, utc_now
from app.db.models import (
    AgentVersion,
    DemoSession,
    IdempotencyRecord,
    IngestionJob,
    KnowledgeDocument,
)
from app.db.readiness import RuntimeResources
from app.domain.enums import DocumentStatus, IngestionState, Role, VersionState
from app.providers.contracts import ProviderTimeoutError

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 100
CHUNK_TARGET = 700
CHUNK_OVERLAP = 120
EMBEDDING_BATCH_SIZE = 32
COLLECTION_NAME = "knowledge_chunks"
ACTIVE_STATES = {
    IngestionState.UPLOADED.value,
    IngestionState.EXTRACTING.value,
    IngestionState.CHUNKING.value,
    IngestionState.EMBEDDING.value,
}
RETRYABLE_ERRORS = {"EMBEDDING_PROVIDER_FAILED", "INGESTION_TIMEOUT", "SERVICE_RESTARTED"}
MEDIA_TYPES = {
    "pdf": {"application/pdf"},
    "txt": {"text/plain"},
    "md": {"text/markdown", "text/plain"},
}


class IngestionFailure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    text: str
    page_number: int
    chunk_index: int
    text_sha256: str


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    id: str
    text: str
    page_number: int
    filename: str
    similarity: float


def _require_student_draft(db: Session, session: DemoSession, version_id: str) -> AgentVersion:
    if session.role != Role.STUDENT.value:
        raise ApiError(403, "STUDENT_ROLE_REQUIRED", "Switch to Student mode for this action.")
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    if version.state != VersionState.DRAFT.value:
        raise ApiError(409, "VERSION_IMMUTABLE", "Only a Draft version can change knowledge.")
    return version


def _safe_filename(filename: str | None) -> tuple[str, str]:
    if not filename or len(filename) > 255 or Path(filename).name != filename:
        raise ApiError(422, "UNSAFE_FILENAME", "Choose a file with a simple filename.")
    if any(ord(char) < 32 for char in filename):
        raise ApiError(422, "UNSAFE_FILENAME", "Choose a file with a simple filename.")
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in MEDIA_TYPES:
        raise ApiError(415, "UNSUPPORTED_FILE_TYPE", "Upload a PDF, TXT, or Markdown file.")
    return filename, extension


def validate_upload(
    filename: str | None, media_type: str | None, content: bytes
) -> tuple[str, str]:
    safe_name, extension = _safe_filename(filename)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "FILE_TOO_LARGE", "Files must be 15 MB or smaller.")
    if not content:
        raise ApiError(422, "EMPTY_FILE", "The selected file is empty.")
    normalized_media = (media_type or "").split(";", 1)[0].strip().lower()
    if normalized_media not in MEDIA_TYPES[extension]:
        raise ApiError(
            415,
            "UNSUPPORTED_FILE_TYPE",
            "The file extension and content type do not match.",
        )
    if extension == "pdf" and not content.startswith(b"%PDF-"):
        raise ApiError(415, "UNSUPPORTED_FILE_TYPE", "The selected file is not a valid PDF.")
    return safe_name, extension


def create_upload(
    db: Session,
    resources: RuntimeResources,
    session: DemoSession,
    version_id: str,
    filename: str | None,
    media_type: str | None,
    content: bytes,
    idempotency_key: str | None,
) -> KnowledgeUploadResponse:
    version = _require_student_draft(db, session, version_id)
    safe_name, extension = validate_upload(filename, media_type, content)
    if not idempotency_key or not 8 <= len(idempotency_key) <= 200:
        raise ApiError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "A valid idempotency key is required for upload.",
        )
    now = utc_now()
    scope = f"UPLOAD_KNOWLEDGE:{version.id}"
    key_hash = keyed_hash(resources.settings, "idempotency", idempotency_key)
    request_hash = canonical_hash(
        {
            "filename": safe_name,
            "media_type": media_type,
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    )
    replay = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.session_id == session.id,
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key_hash == key_hash,
        )
    )
    if replay is not None and as_utc(replay.expires_at) > now:
        if replay.request_hash != request_hash:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This request key was already reused.")
        return KnowledgeUploadResponse.model_validate_json(replay.response_body)
    if replay is not None:
        db.delete(replay)

    active_job = db.scalar(select(IngestionJob).where(IngestionJob.state.in_(ACTIVE_STATES)))
    if active_job is not None:
        raise ApiError(409, "INGESTION_IN_PROGRESS", "Wait for the current upload to finish.")

    digest = hashlib.sha256(content).hexdigest()
    duplicate = db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.version_id == version.id,
            KnowledgeDocument.sha256 == digest,
        )
    )
    if duplicate is not None:
        raise ApiError(409, "DUPLICATE_DOCUMENT", "This version already has that document.")

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    uploads_today = int(
        db.scalar(
            select(func.count())
            .select_from(KnowledgeDocument)
            .where(KnowledgeDocument.created_at >= day_start)
        )
        or 0
    )
    if uploads_today >= resources.settings.daily_ingestion_limit:
        raise ApiError(
            429,
            "INGESTION_RATE_LIMITED",
            "The daily upload limit has been reached.",
            retryable=True,
            retry_after_seconds=86400,
        )
    document_id = str(uuid4())
    upload_dir = (resources.settings.uploads_path / document_id).resolve()
    upload_root = resources.settings.uploads_path.resolve()
    try:
        upload_dir.relative_to(upload_root)
    except ValueError as error:
        raise ApiError(500, "UPLOAD_STORAGE_FAILED", "The file could not be stored.") from error
    upload_dir.mkdir(parents=True, exist_ok=False)
    storage_path = upload_dir / f"source.{extension}"
    storage_path.write_bytes(content)

    document = KnowledgeDocument(
        id=document_id,
        version_id=version.id,
        original_filename=safe_name,
        media_type=(media_type or "").split(";", 1)[0].strip().lower(),
        extension=extension,
        byte_size=len(content),
        sha256=digest,
        storage_path=str(storage_path),
        status=DocumentStatus.UPLOADED.value,
        page_count=None,
        chunk_count=None,
        embedding_model=resources.embedding_provider.model,
        error_code=None,
        is_active=0,
        created_at=now,
        ready_at=None,
        retired_at=None,
    )
    job = IngestionJob(
        id=str(uuid4()),
        document_id=document.id,
        state=IngestionState.UPLOADED.value,
        attempt=1,
        progress_completed=0,
        progress_total=0,
        started_at=None,
        heartbeat_at=now,
        finished_at=None,
        error_code=None,
        safe_error_message=None,
        created_at=now,
        updated_at=now,
    )
    db.add(document)
    try:
        db.flush()
        db.add(job)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        storage_path.unlink(missing_ok=True)
        upload_dir.rmdir()
        raise ApiError(
            409, "DUPLICATE_DOCUMENT", "This version already has that document."
        ) from error
    response = KnowledgeUploadResponse(
        document_id=document.id,
        job_id=job.id,
        state=IngestionState.UPLOADED,
        duplicate=False,
    )
    db.add(
        IdempotencyRecord(
            id=str(uuid4()),
            session_id=session.id,
            scope=scope,
            key_hash=key_hash,
            request_hash=request_hash,
            response_status=202,
            response_body=response.model_dump_json(),
            created_at=now,
            expires_at=now + timedelta(hours=resources.settings.idempotency_hours),
        )
    )
    db.commit()
    return response


def _normalize_text(value: str) -> str:
    value = value.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [re.sub(r"[ \t]+", " ", part).strip() for part in re.split(r"\n\s*\n", value)]
    return "\n\n".join(part for part in paragraphs if part)


def _extract(document: KnowledgeDocument) -> list[tuple[int, str]]:
    path = Path(document.storage_path)
    if document.extension == "pdf":
        try:
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise IngestionFailure("PDF_ENCRYPTED", "Encrypted PDFs are not supported.")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise IngestionFailure("PDF_PAGE_LIMIT", "PDFs must contain 100 pages or fewer.")
            pages = [
                (index + 1, _normalize_text(page.extract_text() or ""))
                for index, page in enumerate(reader.pages)
            ]
        except IngestionFailure:
            raise
        except Exception as error:
            raise IngestionFailure(
                "PDF_PARSE_FAILED", "The PDF could not be read safely."
            ) from error
        text_pages = sum(bool(text) for _, text in pages)
        total_chars = sum(len(text) for _, text in pages)
        required_text_pages = math.ceil(len(pages) * 0.8) if pages else 1
        if total_chars < 100 or text_pages < required_text_pages:
            raise IngestionFailure(
                "PDF_SCANNED_OR_EMPTY",
                "This PDF has too little extractable text. OCR is not supported.",
            )
        return pages
    try:
        text = _normalize_text(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise IngestionFailure("TEXT_ENCODING_INVALID", "Text files must use UTF-8.") from error
    if not text:
        raise IngestionFailure("EMPTY_FILE", "The selected file contains no readable text.")
    return [(1, text)]


def _page_windows(text: str) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= CHUNK_TARGET:
            pieces.append(paragraph)
            continue
        start = 0
        while start < len(paragraph):
            end = min(start + CHUNK_TARGET, len(paragraph))
            if end < len(paragraph):
                boundary = paragraph.rfind(" ", start + CHUNK_TARGET // 2, end)
                if boundary > start:
                    end = boundary
            pieces.append(paragraph[start:end].strip())
            start = end

    windows: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}\n\n{piece}".strip() if current else piece
        if current and len(candidate) > CHUNK_TARGET:
            windows.append(current)
            overlap = current[-CHUNK_OVERLAP:].lstrip()
            current = f"{overlap}\n\n{piece}".strip()
        else:
            current = candidate
    if current:
        windows.append(current)
    return windows


def chunk_pages(document_sha256: str, pages: list[tuple[int, str]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page_number, text in pages:
        for chunk_index, window in enumerate(_page_windows(text)):
            text_sha = hashlib.sha256(window.encode("utf-8")).hexdigest()
            stable = f"{document_sha256}:{page_number}:{chunk_index}:{text_sha}"
            chunks.append(
                Chunk(
                    id=hashlib.sha256(stable.encode("ascii")).hexdigest(),
                    text=window,
                    page_number=page_number,
                    chunk_index=chunk_index,
                    text_sha256=text_sha,
                )
            )
    return chunks


def _set_stage(
    resources: RuntimeResources,
    job_id: str,
    state: IngestionState,
    *,
    completed: int = 0,
    total: int = 0,
) -> tuple[KnowledgeDocument, IngestionJob]:
    now = utc_now()
    with resources.session_factory() as db:
        job = db.get(IngestionJob, job_id)
        if job is None:
            raise IngestionFailure("INGESTION_JOB_MISSING", "The ingestion job was not found.")
        document = db.get(KnowledgeDocument, job.document_id)
        if document is None:
            raise IngestionFailure("DOCUMENT_MISSING", "The uploaded document was not found.")
        job.state = state.value
        job.progress_completed = completed
        job.progress_total = total
        job.heartbeat_at = now
        job.updated_at = now
        if job.started_at is None:
            job.started_at = now
        document.status = state.value
        db.commit()
        db.expunge(document)
        db.expunge(job)
        return document, job


def _fail_job(resources: RuntimeResources, job_id: str, failure: IngestionFailure) -> None:
    try:
        collection = resources.chroma.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
        with resources.session_factory() as db:
            job = db.get(IngestionJob, job_id)
            if job is None:
                return
            collection.delete(where={"document_id": job.document_id})
            document = db.get(KnowledgeDocument, job.document_id)
            now = utc_now()
            job.state = IngestionState.FAILED.value
            job.error_code = failure.code
            job.safe_error_message = failure.safe_message
            job.finished_at = now
            job.heartbeat_at = now
            job.updated_at = now
            if document is not None:
                document.status = DocumentStatus.FAILED.value
                document.error_code = failure.code
            db.commit()
    except Exception:
        # The persisted failure is best-effort if storage itself is unavailable.
        return


def process_ingestion_job(resources: RuntimeResources, job_id: str) -> None:
    try:
        document, _ = _set_stage(resources, job_id, IngestionState.EXTRACTING)
        pages = _extract(document)
        with resources.session_factory() as db:
            stored = db.get(KnowledgeDocument, document.id)
            version = db.get(AgentVersion, document.version_id)
            if version is None:
                raise IngestionFailure(
                    "INGESTION_STATE_INVALID", "The Agent version was not found."
                )
            agent_id = version.agent_id
            if stored is not None:
                stored.page_count = len(pages)
                db.commit()

        _set_stage(resources, job_id, IngestionState.CHUNKING)
        chunks = chunk_pages(document.sha256, pages)
        if not chunks:
            raise IngestionFailure("EMPTY_FILE", "The selected file contains no readable text.")

        total_batches = math.ceil(len(chunks) / EMBEDDING_BATCH_SIZE)
        _set_stage(resources, job_id, IngestionState.EMBEDDING, total=total_batches)
        collection = resources.chroma.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
        collection.delete(where={"document_id": document.id})
        for batch_index in range(total_batches):
            batch = chunks[
                batch_index * EMBEDDING_BATCH_SIZE : (batch_index + 1) * EMBEDDING_BATCH_SIZE
            ]
            try:
                embeddings = resources.embedding_provider.embed([chunk.text for chunk in batch])
            except ProviderTimeoutError as error:
                raise IngestionFailure(
                    "INGESTION_TIMEOUT",
                    "Embedding timed out. Retry this upload.",
                ) from error
            except Exception as error:
                raise IngestionFailure(
                    "EMBEDDING_PROVIDER_FAILED",
                    "Embedding service failed. Retry this upload.",
                ) from error
            if len(embeddings) != len(batch):
                raise IngestionFailure(
                    "EMBEDDING_PROVIDER_FAILED",
                    "Embedding service returned an incomplete result. Retry this upload.",
                )
            collection.upsert(
                ids=[chunk.id for chunk in batch],
                documents=[chunk.text for chunk in batch],
                embeddings=cast(Any, embeddings),
                metadatas=[
                    {
                        "agent_id": agent_id,
                        "version_id": document.version_id,
                        "document_id": document.id,
                        "filename": document.original_filename,
                        "page_number": chunk.page_number,
                        "chunk_index": chunk.chunk_index,
                        "text_sha256": chunk.text_sha256,
                        "embedding_model": document.embedding_model,
                    }
                    for chunk in batch
                ],
            )
            _set_stage(
                resources,
                job_id,
                IngestionState.EMBEDDING,
                completed=batch_index + 1,
                total=total_batches,
            )

        now = utc_now()
        retired: KnowledgeDocument | None = None
        with resources.session_factory() as db:
            job = db.get(IngestionJob, job_id)
            stored = db.get(KnowledgeDocument, document.id)
            version = db.get(AgentVersion, document.version_id)
            if job is None or stored is None or version is None:
                raise IngestionFailure("INGESTION_STATE_INVALID", "The ingestion state changed.")
            if version.active_document_id and version.active_document_id != stored.id:
                retired = db.get(KnowledgeDocument, version.active_document_id)
                if retired is not None:
                    retired.status = DocumentStatus.RETIRED.value
                    retired.is_active = 0
                    retired.retired_at = now
            stored.status = DocumentStatus.READY.value
            stored.chunk_count = len(chunks)
            stored.error_code = None
            stored.is_active = 1
            stored.ready_at = now
            version.active_document_id = stored.id
            version.updated_at = now
            job.state = IngestionState.READY.value
            job.progress_completed = total_batches
            job.progress_total = total_batches
            job.finished_at = now
            job.heartbeat_at = now
            job.updated_at = now
            db.commit()
        if retired is not None:
            collection.delete(where={"document_id": retired.id})
            _delete_storage(resources.settings, retired.storage_path)
    except IngestionFailure as failure:
        _fail_job(resources, job_id, failure)
    except Exception:
        _fail_job(
            resources,
            job_id,
            IngestionFailure("INGESTION_FAILED", "The document could not be processed."),
        )


def _job_view(job: IngestionJob) -> IngestionJobView:
    return IngestionJobView(
        id=job.id,
        document_id=job.document_id,
        state=IngestionState(job.state),
        progress=JobProgress(completed=job.progress_completed, total=job.progress_total),
        safe_error=job.safe_error_message,
        error_code=job.error_code,
        retryable=job.error_code in RETRYABLE_ERRORS,
        updated_at=as_utc(job.updated_at),
    )


def get_job(db: Session, job_id: str) -> IngestionJobView:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise ApiError(404, "INGESTION_JOB_NOT_FOUND", "The ingestion job was not found.")
    return _job_view(job)


def get_knowledge_view(db: Session, version: AgentVersion) -> tuple[KnowledgeStatus, KnowledgeView]:
    active = (
        db.get(KnowledgeDocument, version.active_document_id)
        if version.active_document_id
        else None
    )
    latest = db.scalar(
        select(IngestionJob)
        .join(KnowledgeDocument, IngestionJob.document_id == KnowledgeDocument.id)
        .where(KnowledgeDocument.version_id == version.id)
        .order_by(IngestionJob.created_at.desc())
    )
    status: KnowledgeStatus
    if latest is not None and latest.state in ACTIVE_STATES:
        status = "PROCESSING"
    elif latest is not None and latest.state == IngestionState.FAILED.value:
        status = "FAILED"
    elif active is not None and active.status == DocumentStatus.READY.value:
        status = "READY"
    else:
        status = "NOT_ADDED"
    active_view = None
    if active is not None:
        active_view = KnowledgeDocumentView(
            id=active.id,
            original_filename=active.original_filename,
            status=active.status,
            page_count=active.page_count,
            chunk_count=active.chunk_count,
            sha256=active.sha256,
            embedding_model=active.embedding_model,
            ready_at=as_utc(active.ready_at) if active.ready_at else None,
        )
    return status, KnowledgeView(
        active_document=active_view,
        latest_job=_job_view(latest) if latest is not None else None,
    )


def retry_job(
    db: Session,
    resources: RuntimeResources,
    session: DemoSession,
    job_id: str,
) -> KnowledgeUploadResponse:
    previous = db.get(IngestionJob, job_id)
    if previous is None:
        raise ApiError(404, "INGESTION_JOB_NOT_FOUND", "The ingestion job was not found.")
    document = db.get(KnowledgeDocument, previous.document_id)
    if document is None:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "The uploaded document was not found.")
    _require_student_draft(db, session, document.version_id)
    if previous.state != IngestionState.FAILED.value:
        raise ApiError(409, "INGESTION_NOT_RETRYABLE", "Only a failed upload can be retried.")
    if previous.error_code not in RETRYABLE_ERRORS:
        raise ApiError(409, "INGESTION_NOT_RETRYABLE", "Upload a corrected file instead.")
    if db.scalar(select(IngestionJob).where(IngestionJob.state.in_(ACTIVE_STATES))) is not None:
        raise ApiError(409, "INGESTION_IN_PROGRESS", "Wait for the current upload to finish.")
    resources.chroma.get_or_create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    ).delete(where={"document_id": document.id})
    now = utc_now()
    attempt = (
        int(
            db.scalar(
                select(func.max(IngestionJob.attempt)).where(
                    IngestionJob.document_id == document.id
                )
            )
            or 0
        )
        + 1
    )
    job = IngestionJob(
        id=str(uuid4()),
        document_id=document.id,
        state=IngestionState.UPLOADED.value,
        attempt=attempt,
        progress_completed=0,
        progress_total=0,
        started_at=None,
        heartbeat_at=now,
        finished_at=None,
        error_code=None,
        safe_error_message=None,
        created_at=now,
        updated_at=now,
    )
    document.status = DocumentStatus.UPLOADED.value
    document.error_code = None
    db.add(job)
    db.commit()
    return KnowledgeUploadResponse(
        document_id=document.id,
        job_id=job.id,
        state=IngestionState.UPLOADED,
        duplicate=False,
    )


def _delete_storage(settings: Settings, storage_path: str) -> None:
    path = Path(storage_path).resolve()
    root = settings.uploads_path.resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise IngestionFailure("UNSAFE_STORAGE_PATH", "Stored file path is invalid.") from error
    if path.is_symlink():
        raise IngestionFailure("UNSAFE_STORAGE_PATH", "Stored file path is invalid.")
    path.unlink(missing_ok=True)
    parent = path.parent
    if parent != root:
        with suppress(OSError):
            parent.rmdir()


def delete_document(
    db: Session,
    resources: RuntimeResources,
    session: DemoSession,
    version_id: str,
    document_id: str,
) -> None:
    version = _require_student_draft(db, session, version_id)
    document = db.get(KnowledgeDocument, document_id)
    if document is None or document.version_id != version.id:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "The uploaded document was not found.")
    active = db.scalar(
        select(IngestionJob).where(
            IngestionJob.document_id == document.id,
            IngestionJob.state.in_(ACTIVE_STATES),
        )
    )
    if active is not None:
        raise ApiError(409, "INGESTION_IN_PROGRESS", "Wait for processing to finish.")
    resources.chroma.get_or_create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    ).delete(where={"document_id": document.id})
    _delete_storage(resources.settings, document.storage_path)
    if version.active_document_id == document.id:
        version.active_document_id = None
    db.delete(document)
    db.commit()


def retrieve(
    resources: RuntimeResources,
    version_id: str,
    query: str,
) -> list[RetrievedChunk]:
    with resources.session_factory() as db:
        version = db.get(AgentVersion, version_id)
        if version is None or not version.active_document_id:
            return []
        document = db.get(KnowledgeDocument, version.active_document_id)
        if document is None or document.status != DocumentStatus.READY.value:
            return []
        document_id = document.id
    embedding = resources.embedding_provider.embed([query])[0]
    collection = resources.chroma.get_or_create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )
    result = collection.query(
        query_embeddings=[embedding],
        n_results=resources.settings.rag_top_k,
        where={
            "$and": [
                {"version_id": {"$eq": version_id}},
                {"document_id": {"$eq": document_id}},
            ]
        },
        include=["documents", "metadatas", "distances"],
    )
    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = cast(list[dict[str, Any]], (result.get("metadatas") or [[]])[0])
    distances = (result.get("distances") or [[]])[0]
    chunks: list[RetrievedChunk] = []
    for chunk_id, text, metadata, distance in zip(
        ids, documents, metadatas, distances, strict=True
    ):
        similarity = 1.0 - float(distance)
        if similarity < resources.settings.rag_min_similarity:
            continue
        chunks.append(
            RetrievedChunk(
                id=str(chunk_id),
                text=str(text),
                page_number=int(metadata["page_number"]),
                filename=str(metadata["filename"]),
                similarity=similarity,
            )
        )
    return chunks
