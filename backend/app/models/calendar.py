"""SQLAlchemy Calendar models: CalendarPlan + CalendarSlot."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid

from app.database import Base


class CalendarPlan(Base):
    """One plan per brand per month."""

    __tablename__ = "calendar_plans"
    __table_args__ = (
        UniqueConstraint("user_id", "brand_id", "year", "month", name="uq_plan_user_brand_month"),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, nullable=False, index=True)
    brand_id = Column(Uuid, ForeignKey("brands.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    status = Column(String(20), default="draft", nullable=False)  # draft | active | archived
    planner_session_id = Column(Uuid, ForeignKey("sessions.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CalendarSlot(Base):
    """One slot per post-date within a plan."""

    __tablename__ = "calendar_slots"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id = Column(Uuid, ForeignKey("calendar_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_date = Column(Date, nullable=False)
    event_name = Column(String(200), nullable=True)
    event_type = Column(String(50), nullable=True)  # festival, trending, brand, regular
    post_idea = Column(Text, nullable=True)
    post_type = Column(String(50), default="single_post", nullable=False)
    status = Column(String(20), default="suggested", nullable=False)  # suggested | approved | generating | generated | skipped
    session_id = Column(Uuid, ForeignKey("sessions.id"), nullable=True)
    generated_image = Column(String(500), nullable=True)
    caption = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
