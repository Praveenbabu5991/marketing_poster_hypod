"""Brand CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.brand import BrandCreate, BrandResponse, BrandUpdate
from app.security.dependencies import require_authenticated_user
from app.security.models import UserDetails
from app.services import brand_service

router = APIRouter()


@router.get("", response_model=list[BrandResponse])
async def list_brands(
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    return await brand_service.list_brands(db, user.user_id)


@router.post("", response_model=BrandResponse, status_code=201)
async def create_brand(
    data: BrandCreate,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    return await brand_service.create_brand(db, user.user_id, data)


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: UUID,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    brand = await brand_service.get_brand(db, brand_id, user.user_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.put("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: UUID,
    data: BrandUpdate,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    brand = await brand_service.update_brand(db, brand_id, user.user_id, data)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.delete("/{brand_id}", status_code=204)
async def delete_brand(
    brand_id: UUID,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await brand_service.delete_brand(db, brand_id, user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Brand not found")
