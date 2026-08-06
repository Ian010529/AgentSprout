"""Shared Chat precondition queries without command or presentation behavior."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AgentVersion, KnowledgeDocument
from app.domain.enums import DocumentStatus
from app.domain.errors import ApiError


def require_ready_version(db: Session, version_id: str) -> AgentVersion:
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise ApiError(404, "VERSION_NOT_FOUND", "The Agent version was not found.")
    document = (
        db.get(KnowledgeDocument, version.active_document_id)
        if version.active_document_id
        else None
    )
    if document is None or document.status != DocumentStatus.READY.value:
        raise ApiError(409, "KNOWLEDGE_NOT_READY", "Add a Ready knowledge source before testing.")
    return version
