"""Usage logging model for per-user, per-model API cost tracking."""

import uuid
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy import Uuid, JSON
from sqlalchemy.sql import func
from app.database import Base


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, nullable=False, index=True)
    session_id = Column(Uuid, ForeignKey("sessions.id"), nullable=True)

    # Category: 'text', 'image', 'video', 'search'
    action_type = Column(String(50), nullable=False, index=True)

    # Free-form model name — no enum, no migration needed for new models
    model_name = Column(String(200), nullable=False, index=True)

    # Tool that triggered this log (e.g. "generate_image", "orchestrator_llm")
    tool_name = Column(String(100), nullable=True)

    # "success" or "error"
    status = Column(String(20), nullable=False, default="success")

    # Calculated USD cost
    cost_usd = Column(Float, nullable=False, default=0.0)

    # Token counts (for LLM calls)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)

    # Unit count (images generated, API calls, etc.)
    unit_count = Column(Integer, nullable=False, default=1)

    # Video duration for Veo billing
    video_duration_seconds = Column(Integer, nullable=True)

    # Error message if status == "error"
    error_message = Column(Text, nullable=True)

    # Arbitrary metadata
    metadata_json = Column(JSON, nullable=True, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
