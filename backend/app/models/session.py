"""SQLAlchemy Session model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Uuid

from app.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, nullable=False, index=True)
    brand_id = Column(Uuid, ForeignKey("brands.id"), nullable=False, index=True)
    agent_type = Column(String(50), nullable=False)
    thread_id = Column(String(255), unique=True, nullable=False)
    status = Column(String(20), default="active", nullable=False)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
