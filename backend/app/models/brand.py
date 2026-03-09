"""SQLAlchemy Brand model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, JSON, String, Text, Uuid

from app.database import Base


class Brand(Base):
    __tablename__ = "brands"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    industry = Column(String(100), nullable=True)
    overview = Column(Text, nullable=True)
    tone = Column(String(50), nullable=False)
    target_audience = Column(Text, nullable=True)
    products_services = Column(Text, nullable=True)
    logo_path = Column(String(500), nullable=True)
    colors = Column(JSON, nullable=True, default=list)
    product_images = Column(JSON, nullable=True, default=list)
    style_reference_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
