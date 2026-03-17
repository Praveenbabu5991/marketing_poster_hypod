import uuid
import enum
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base

class AIModelName(str, enum.Enum):
    # Text Models
    GEMINI_FLASH = "google_genai/gemini-2.5-flash"
    GEMINI_PRO = "google_genai/gemini-1.5-pro"
    
    # Image Models
    IMAGEN_3 = "gemini-3-pro-image-preview"
    
    # Video Models
    VEO_3 = "veo-3.1-generate-preview"
    
    # Search/Utility
    WEB_SEARCH = "web_search_utility"

class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=True)
    
    # Category: 'text', 'image', 'video'
    action_type = Column(String(50), nullable=False, index=True)
    
    # Use the Enum for strict model tracking
    model_name = Column(
        Enum(AIModelName, name="aimodelname_enum", create_type=True), 
        nullable=False, 
        index=True
    )
    
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    unit_count = Column(Integer, nullable=False, default=1)
    
    metadata_json = Column(JSONB, nullable=True, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
