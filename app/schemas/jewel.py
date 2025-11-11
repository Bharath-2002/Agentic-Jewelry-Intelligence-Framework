from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class JewelResponse(BaseModel):
    """Schema for jewel response."""
    id: UUID
    name: str
    source_url: str
    jewel_type: Optional[str] = None
    metal: Optional[str] = None
    gemstone: Optional[str] = None
    gemstone_color: Optional[str] = None
    metal_color: Optional[str] = None
    color: Optional[str] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    inferred_attributes: Optional[dict] = None
    vibe: Optional[str] = None
    summary: Optional[str] = None
    images: Optional[List[str]] = None
    raw_metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JewelListResponse(BaseModel):
    """Schema for paginated jewel list response."""
    items: List[JewelResponse]
    total: int
    limit: int
    offset: int
