from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from typing import Optional
from app.database import get_db
from app.models.jewel import Jewel
from app.schemas.jewel import JewelResponse, JewelListResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/jewels", response_model=JewelListResponse)
async def list_jewels(
    vibe: Optional[str] = Query(None, description="Filter by vibe"),
    metal: Optional[str] = Query(None, description="Filter by metal type"),
    jewel_type: Optional[str] = Query(None, description="Filter by jewelry type"),
    gemstone: Optional[str] = Query(None, description="Filter by gemstone"),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a paginated list of jewels with optional filters.
    """
    # Build query with filters
    query = select(Jewel)

    if vibe:
        query = query.where(Jewel.vibe == vibe)
    if metal:
        query = query.where(Jewel.metal.ilike(f"%{metal}%"))
    if jewel_type:
        query = query.where(Jewel.jewel_type.ilike(f"%{jewel_type}%"))
    if gemstone:
        query = query.where(Jewel.gemstone.ilike(f"%{gemstone}%"))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.limit(limit).offset(offset).order_by(Jewel.created_at.desc())
    result = await db.execute(query)
    jewels = result.scalars().all()

    return JewelListResponse(
        items=[JewelResponse.model_validate(jewel) for jewel in jewels],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/jewels/{jewel_id}", response_model=JewelResponse)
async def get_jewel(
    jewel_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single jewel by its ID.
    """
    result = await db.execute(select(Jewel).where(Jewel.id == jewel_id))
    jewel = result.scalar_one_or_none()

    if not jewel:
        raise HTTPException(status_code=404, detail="Jewel not found")

    return JewelResponse.model_validate(jewel)
