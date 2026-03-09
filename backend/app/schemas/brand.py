"""Pydantic schemas for brand endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BrandCreate(BaseModel):
    name: str = Field(..., max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    overview: Optional[str] = None
    tone: str = Field(..., max_length=50)
    target_audience: Optional[str] = None
    products_services: Optional[str] = None
    logo_path: Optional[str] = None
    colors: list[str] = Field(default_factory=list)
    product_images: list[str] = Field(default_factory=list)
    style_reference_url: Optional[str] = None


class BrandUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    overview: Optional[str] = None
    tone: Optional[str] = Field(None, max_length=50)
    target_audience: Optional[str] = None
    products_services: Optional[str] = None
    logo_path: Optional[str] = None
    colors: Optional[list[str]] = None
    product_images: Optional[list[str]] = None
    style_reference_url: Optional[str] = None


class BrandResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    industry: Optional[str]
    overview: Optional[str]
    tone: str
    target_audience: Optional[str]
    products_services: Optional[str]
    logo_path: Optional[str]
    colors: list[str]
    product_images: list[str]
    style_reference_url: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
