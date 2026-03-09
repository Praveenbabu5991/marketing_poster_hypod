"""Brand CRUD business logic."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.schemas.brand import BrandCreate, BrandUpdate


async def create_brand(db: AsyncSession, user_id: UUID, data: BrandCreate) -> Brand:
    brand = Brand(user_id=user_id, **data.model_dump())
    db.add(brand)
    await db.flush()
    await db.refresh(brand)
    return brand


async def get_brand(db: AsyncSession, brand_id: UUID, user_id: UUID) -> Brand | None:
    result = await db.execute(
        select(Brand).where(Brand.id == brand_id, Brand.user_id == user_id, Brand.is_active == True)
    )
    return result.scalar_one_or_none()


async def list_brands(db: AsyncSession, user_id: UUID) -> list[Brand]:
    result = await db.execute(
        select(Brand).where(Brand.user_id == user_id, Brand.is_active == True).order_by(Brand.updated_at.desc())
    )
    return list(result.scalars().all())


async def update_brand(db: AsyncSession, brand_id: UUID, user_id: UUID, data: BrandUpdate) -> Brand | None:
    brand = await get_brand(db, brand_id, user_id)
    if not brand:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(brand, key, value)
    await db.flush()
    await db.refresh(brand)
    return brand


async def delete_brand(db: AsyncSession, brand_id: UUID, user_id: UUID) -> bool:
    brand = await get_brand(db, brand_id, user_id)
    if not brand:
        return False
    brand.is_active = False
    await db.flush()
    return True
