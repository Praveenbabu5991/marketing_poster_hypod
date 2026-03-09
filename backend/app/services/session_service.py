"""Session CRUD business logic."""

import uuid
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.schemas.session import SessionCreate


async def create_session(db: AsyncSession, user_id: UUID, data: SessionCreate) -> Session:
    thread_id = f"thread_{uuid.uuid4().hex}"
    session = Session(
        user_id=user_id,
        brand_id=data.brand_id,
        agent_type=data.agent_type,
        thread_id=thread_id,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: UUID, user_id: UUID) -> Session | None:
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    user_id: UUID,
    brand_id: Optional[UUID] = None,
    agent_type: Optional[str] = None,
) -> list[Session]:
    query = select(Session).where(
        Session.user_id == user_id,
        Session.status != "archived",
    )
    if brand_id:
        query = query.where(Session.brand_id == brand_id)
    if agent_type:
        query = query.where(Session.agent_type == agent_type)
    query = query.order_by(Session.updated_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_session_title(
    db: AsyncSession, session_id: UUID, user_id: UUID, title: str
) -> Session | None:
    session = await get_session(db, session_id, user_id)
    if not session:
        return None
    session.title = title
    await db.flush()
    await db.refresh(session)
    return session


async def archive_session(db: AsyncSession, session_id: UUID, user_id: UUID) -> bool:
    session = await get_session(db, session_id, user_id)
    if not session:
        return False
    session.status = "archived"
    await db.flush()
    return True
