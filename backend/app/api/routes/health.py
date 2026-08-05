from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, status
from pydantic import BaseModel
from starlette.responses import JSONResponse

from app.db.readiness import RuntimeResources, readiness_checks

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["agentsprout-api"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, str]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="agentsprout-api")


@router.get("/ready", response_model=ReadinessResponse)
def ready(request: Request) -> ReadinessResponse | JSONResponse:
    resources: RuntimeResources = request.app.state.resources
    checks = readiness_checks(resources)
    if all(result == "ok" for result in checks.values()):
        return ReadinessResponse(status="ready", checks=checks)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ReadinessResponse(status="not_ready", checks=checks).model_dump(),
    )
