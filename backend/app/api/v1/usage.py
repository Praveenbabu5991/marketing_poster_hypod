"""Usage monitoring API endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.usage import UsageHistoryResponse, UsageSummaryResponse
from app.security.dependencies import require_authenticated_user
from app.security.models import UserDetails
from app.services import usage_service

router = APIRouter()


@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    start_date: Optional[date] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated usage summary grouped by model and action type."""
    return await usage_service.get_usage_summary(
        db=db,
        user_id=user.user_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/history", response_model=UsageHistoryResponse)
async def get_usage_history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action_type: Optional[str] = Query(None, description="Filter by action type (text, image, video, search)"),
    model_name: Optional[str] = Query(None, description="Filter by model name"),
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated usage log history."""
    return await usage_service.get_usage_history(
        db=db,
        user_id=user.user_id,
        limit=limit,
        offset=offset,
        action_type=action_type,
        model_name=model_name,
    )
