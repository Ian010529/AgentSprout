from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.studio_agents import router as studio_agents_router
from app.api.routes.studio_knowledge import router as studio_knowledge_router
from app.api.routes.studio_session import router as studio_session_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(studio_session_router)
api_router.include_router(studio_agents_router)
api_router.include_router(studio_knowledge_router)
