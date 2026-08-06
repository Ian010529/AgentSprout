from __future__ import annotations

import asyncio
from typing import Annotated, cast

from fastapi import APIRouter, Header, Request, status

from app.api.dependencies import CurrentSession, DatabaseSession, MutationSession, RuntimeResource
from app.api.schemas import (
    EvaluationCaseDetail,
    EvaluationCaseList,
    EvaluationCreateResponse,
    EvaluationRunList,
    EvaluationRunView,
)
from app.db.readiness import RuntimeResources
from app.domain.enums import EvaluationCategory, EvaluationState
from app.services.evaluation import (
    create_evaluation,
    get_case_result,
    get_evaluation,
    list_case_results,
    list_evaluations,
    process_evaluation,
)

router = APIRouter(prefix="/studio", tags=["studio-evaluations"])


def _schedule(request: Request, resources: RuntimeResources, run_id: str) -> None:
    run_ids = cast(set[str], request.app.state.evaluation_run_ids)
    if run_id in run_ids:
        return
    run_ids.add(run_id)
    task = asyncio.create_task(asyncio.to_thread(process_evaluation, resources, run_id))
    tasks = cast(set[asyncio.Task[None]], request.app.state.evaluation_tasks)
    tasks.add(task)

    def complete(completed: asyncio.Task[None]) -> None:
        tasks.discard(completed)
        run_ids.discard(run_id)

    task.add_done_callback(complete)


@router.post(
    "/versions/{version_id}/evaluations",
    response_model=EvaluationCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_evaluation(
    request: Request,
    version_id: str,
    db: DatabaseSession,
    resources: RuntimeResource,
    session: MutationSession,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> EvaluationCreateResponse:
    response = create_evaluation(db, resources, session, version_id, idempotency_key)
    if response.state == EvaluationState.QUEUED:
        _schedule(request, resources, response.evaluation_run_id)
    return response


@router.get("/evaluations/{run_id}", response_model=EvaluationRunView)
def read_evaluation(
    run_id: str, db: DatabaseSession, _session: CurrentSession
) -> EvaluationRunView:
    return get_evaluation(db, _session, run_id)


@router.get("/versions/{version_id}/evaluations", response_model=EvaluationRunList)
def read_version_evaluations(
    version_id: str, db: DatabaseSession, session: CurrentSession
) -> EvaluationRunList:
    return list_evaluations(db, session, version_id)


@router.get("/evaluations/{run_id}/cases", response_model=EvaluationCaseList)
def read_evaluation_cases(
    run_id: str,
    db: DatabaseSession,
    _session: CurrentSession,
    category: EvaluationCategory | None = None,
) -> EvaluationCaseList:
    return list_case_results(db, _session, run_id, category)


@router.get("/evaluation-cases/{result_id}", response_model=EvaluationCaseDetail)
def read_evaluation_case(
    result_id: str, db: DatabaseSession, _session: CurrentSession
) -> EvaluationCaseDetail:
    return get_case_result(db, _session, result_id)
