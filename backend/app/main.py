from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.api.errors import ApiError
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.request_id import RequestIdMiddleware
from app.core.startup import run_startup_maintenance
from app.db.engine import create_session_factory, create_sqlite_engine
from app.db.readiness import RuntimeResources, create_chroma_client
from app.providers.contracts import ChatProvider, EmbeddingProvider, JudgeProvider
from app.providers.openai_chat import OpenAIChatProvider
from app.providers.openai_embeddings import OpenAIEmbeddingProvider
from app.providers.openai_judge import OpenAIJudgeProvider
from app.services.public_store import TransientStore

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    chat_provider: ChatProvider | None = None,
    judge_provider: JudgeProvider | None = None,
) -> FastAPI:
    configure_logging()
    runtime_settings = settings or get_settings()
    runtime_settings.create_runtime_directories()
    engine = create_sqlite_engine(runtime_settings)
    resources = RuntimeResources(
        settings=runtime_settings,
        engine=engine,
        chroma=create_chroma_client(runtime_settings),
        session_factory=create_session_factory(engine),
        embedding_provider=embedding_provider or OpenAIEmbeddingProvider(runtime_settings),
        chat_provider=chat_provider or OpenAIChatProvider(runtime_settings),
        judge_provider=judge_provider or OpenAIJudgeProvider(runtime_settings),
    )

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncGenerator[None]:
        run_startup_maintenance(resources)
        yield

    application = FastAPI(
        title="AgentSprout Studio API",
        version="0.1.0",
        docs_url="/api/docs" if runtime_settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.resources = resources
    application.state.ingestion_tasks = set()
    application.state.ingestion_job_ids = set()
    application.state.chat_tasks = set()
    application.state.chat_run_ids = set()
    application.state.evaluation_tasks = set()
    application.state.evaluation_run_ids = set()
    application.state.public_tasks = set()
    application.state.public_run_ids = set()
    application.state.transient_store = TransientStore()
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "X-Request-ID",
            "X-CSRF-Token",
            "X-Public-Run-Token",
            "Idempotency-Key",
        ],
    )
    application.include_router(api_router, prefix="/api/v1")

    async def api_error(request: Request, error: Exception) -> JSONResponse:
        if not isinstance(error, ApiError):
            return await unexpected_error(request, error)
        request_id = getattr(request.state, "request_id", "unknown")
        headers = (
            {"Retry-After": str(error.retry_after_seconds)}
            if error.retry_after_seconds is not None
            else None
        )
        return JSONResponse(
            status_code=error.status_code,
            headers=headers,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "request_id": request_id,
                    "retryable": error.retryable,
                    "retry_after_seconds": error.retry_after_seconds,
                    "field_errors": error.field_errors,
                }
            },
        )

    async def validation_error(request: Request, error: Exception) -> JSONResponse:
        if not isinstance(error, RequestValidationError):
            return await unexpected_error(request, error)
        field_errors: dict[str, str] = {}
        for item in error.errors():
            location = ".".join(str(part) for part in item["loc"] if part not in {"body", "query"})
            field_errors[location or "request"] = str(item["msg"])
        return await api_error(
            request,
            ApiError(
                422,
                "VALIDATION_ERROR",
                "Check the highlighted fields and try again.",
                field_errors=field_errors,
            ),
        )

    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception("Unhandled application error", extra={"request_id": request_id})
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "The service could not complete the request.",
                    "request_id": request_id,
                    "retryable": False,
                    "retry_after_seconds": None,
                    "field_errors": {},
                }
            },
        )

    application.add_exception_handler(ApiError, api_error)
    application.add_exception_handler(RequestValidationError, validation_error)
    application.add_exception_handler(Exception, unexpected_error)
    return application
