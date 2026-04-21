"""API v1 router: include all sub-routers."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    agents,
    billing,
    brands,
    calendar,
    chat,
    credits,
    sessions,
    upload,
    usage,
)

api_router = APIRouter()

api_router.include_router(brands.router, prefix="/brands", tags=["brands"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
api_router.include_router(credits.router, prefix="/credits", tags=["credits"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
