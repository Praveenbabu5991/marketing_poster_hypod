"""Session management endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.session import SessionCreate, SessionResponse, SessionUpdate
from app.security.dependencies import require_authenticated_user
from app.security.models import UserDetails
from app.services import session_service
from agents.registry import AGENT_CONFIGS

router = APIRouter()


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    brand_id: Optional[UUID] = None,
    agent_type: Optional[str] = None,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    return await session_service.list_sessions(db, user.user_id, brand_id, agent_type)


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    data: SessionCreate,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    if data.agent_type not in AGENT_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {data.agent_type}")
    return await session_service.create_session(db, user.user_id, data)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.get_session(db, session_id, user.user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: UUID,
    data: SessionUpdate,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    if data.title is None:
        raise HTTPException(status_code=400, detail="Nothing to update")
    session = await session_service.update_session_title(db, session_id, user.user_id, data.title)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}", status_code=204)
async def archive_session(
    session_id: UUID,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    archived = await session_service.archive_session(db, session_id, user.user_id)
    if not archived:
        raise HTTPException(status_code=404, detail="Session not found")
