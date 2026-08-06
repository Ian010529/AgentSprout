from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, status

from app.api.dependencies import CurrentSession, DatabaseSession, MutationSession, RuntimeResource
from app.api.schemas import (
    ApproveVersion,
    NextVersion,
    RequestChanges,
    ReviewDecisionResponse,
    VersionComparison,
    VersionDetail,
)
from app.services.review import (
    approve_version,
    compare_versions,
    create_next_version,
    request_changes,
)

router = APIRouter(prefix="/studio", tags=["studio-review"])


@router.post("/versions/{version_id}/request-changes", response_model=ReviewDecisionResponse)
def change_request(
    version_id: str,
    payload: RequestChanges,
    db: DatabaseSession,
    session: MutationSession,
) -> ReviewDecisionResponse:
    return request_changes(db, session, version_id, payload)


@router.post(
    "/versions/{version_id}/next-version",
    response_model=VersionDetail,
    status_code=status.HTTP_201_CREATED,
)
def next_version(
    version_id: str,
    payload: NextVersion,
    db: DatabaseSession,
    resources: RuntimeResource,
    session: MutationSession,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> VersionDetail:
    return create_next_version(db, resources, session, version_id, payload, idempotency_key)


@router.post("/versions/{version_id}/approve", response_model=ReviewDecisionResponse)
def approve(
    version_id: str,
    payload: ApproveVersion,
    db: DatabaseSession,
    resources: RuntimeResource,
    session: MutationSession,
) -> ReviewDecisionResponse:
    return approve_version(db, resources, session, version_id, payload)


@router.get(
    "/versions/{left_version_id}/compare/{right_version_id}",
    response_model=VersionComparison,
)
def compare(
    left_version_id: str,
    right_version_id: str,
    left_run_id: str,
    right_run_id: str,
    db: DatabaseSession,
    session: CurrentSession,
) -> VersionComparison:
    return compare_versions(
        db, session, left_version_id, right_version_id, left_run_id, right_run_id
    )
