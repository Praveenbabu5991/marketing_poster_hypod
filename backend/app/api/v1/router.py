"""API v1 router: include all sub-routers."""

from fastapi import APIRouter

from app.api.v1 import agents, brands, chat, sessions, upload

api_router = APIRouter()

api_router.include_router(brands.router, prefix="/brands", tags=["brands"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
