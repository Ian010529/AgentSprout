from __future__ import annotations

import logging

from sqlalchemy import inspect, select

from app.core.security import utc_now
from app.db.models import IngestionJob, KnowledgeDocument
from app.db.readiness import RuntimeResources
from app.domain.enums import DocumentStatus, IngestionState

logger = logging.getLogger(__name__)


def run_startup_maintenance(resources: RuntimeResources) -> None:
    if not inspect(resources.engine).has_table("ingestion_jobs"):
        logger.info("Startup maintenance skipped before knowledge migration")
        return
    now = utc_now()
    active_states = [
        IngestionState.UPLOADED.value,
        IngestionState.EXTRACTING.value,
        IngestionState.CHUNKING.value,
        IngestionState.EMBEDDING.value,
    ]
    with resources.session_factory() as db:
        jobs = list(db.scalars(select(IngestionJob).where(IngestionJob.state.in_(active_states))))
        for job in jobs:
            job.state = IngestionState.FAILED.value
            job.error_code = "SERVICE_RESTARTED"
            job.safe_error_message = "The service restarted. Retry this upload."
            job.finished_at = now
            job.updated_at = now
            document = db.get(KnowledgeDocument, job.document_id)
            if document is not None:
                document.status = DocumentStatus.FAILED.value
                document.error_code = "SERVICE_RESTARTED"
        db.commit()
    logger.info("Startup maintenance complete")
