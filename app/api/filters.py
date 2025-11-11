"""API endpoints for filter metadata."""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from app.database import get_db
from app.models.jewel import Jewel
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/filters")
async def get_filter_options(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, List[str]]:
    """
    Get all unique filter values for jewel attributes.

    This endpoint returns all distinct values for each filterable attribute
    to populate dropdown filters in the frontend.

    Returns:
        Dictionary with filter options for each attribute:
        - jewel_types: List of unique jewelry types
        - metals: List of unique metal types
        - gemstones: List of unique gemstone types
        - gemstone_colors: List of unique gemstone colors
        - metal_colors: List of unique metal colors
        - vibes: List of unique vibe categories
        - colors: List of unique colors
        - currencies: List of unique price currencies
    """
    try:
        # Get distinct jewel types
        jewel_types_result = await db.execute(
            select(distinct(Jewel.jewel_type))
            .where(Jewel.jewel_type.isnot(None))
            .order_by(Jewel.jewel_type)
        )
        jewel_types = [row[0] for row in jewel_types_result.fetchall()]

        # Get distinct metals
        metals_result = await db.execute(
            select(distinct(Jewel.metal))
            .where(Jewel.metal.isnot(None))
            .order_by(Jewel.metal)
        )
        metals = [row[0] for row in metals_result.fetchall()]

        # Get distinct gemstones
        gemstones_result = await db.execute(
            select(distinct(Jewel.gemstone))
            .where(Jewel.gemstone.isnot(None))
            .order_by(Jewel.gemstone)
        )
        gemstones = [row[0] for row in gemstones_result.fetchall()]

        # Get distinct gemstone colors
        gemstone_colors_result = await db.execute(
            select(distinct(Jewel.gemstone_color))
            .where(Jewel.gemstone_color.isnot(None))
            .order_by(Jewel.gemstone_color)
        )
        gemstone_colors = [row[0] for row in gemstone_colors_result.fetchall()]

        # Get distinct metal colors
        metal_colors_result = await db.execute(
            select(distinct(Jewel.metal_color))
            .where(Jewel.metal_color.isnot(None))
            .order_by(Jewel.metal_color)
        )
        metal_colors = [row[0] for row in metal_colors_result.fetchall()]

        # Get distinct vibes
        vibes_result = await db.execute(
            select(distinct(Jewel.vibe))
            .where(Jewel.vibe.isnot(None))
            .order_by(Jewel.vibe)
        )
        vibes = [row[0] for row in vibes_result.fetchall()]

        # Get distinct colors
        colors_result = await db.execute(
            select(distinct(Jewel.color))
            .where(Jewel.color.isnot(None))
            .order_by(Jewel.color)
        )
        colors = [row[0] for row in colors_result.fetchall()]

        # Get distinct currencies
        currencies_result = await db.execute(
            select(distinct(Jewel.price_currency))
            .where(Jewel.price_currency.isnot(None))
            .order_by(Jewel.price_currency)
        )
        currencies = [row[0] for row in currencies_result.fetchall()]

        # Get price range
        price_range_result = await db.execute(
            select(
                func.min(Jewel.price_amount),
                func.max(Jewel.price_amount)
            ).where(Jewel.price_amount.isnot(None))
        )
        min_price, max_price = price_range_result.fetchone()

        # Get total count
        count_result = await db.execute(select(func.count(Jewel.id)))
        total_count = count_result.scalar()

        logger.info(f"Retrieved filter options: {total_count} total jewels")

        return {
            "jewel_types": jewel_types,
            "metals": metals,
            "gemstones": gemstones,
            "gemstone_colors": gemstone_colors,
            "metal_colors": metal_colors,
            "vibes": vibes,
            "colors": colors,
            "currencies": currencies,
            "price_range": {
                "min": float(min_price) if min_price else None,
                "max": float(max_price) if max_price else None
            },
            "total_count": total_count
        }

    except Exception as e:
        logger.error(f"Error retrieving filter options: {str(e)}")
        # Return empty filters on error
        return {
            "jewel_types": [],
            "metals": [],
            "gemstones": [],
            "gemstone_colors": [],
            "metal_colors": [],
            "vibes": [],
            "colors": [],
            "currencies": [],
            "price_range": {"min": None, "max": None},
            "total_count": 0
        }


@router.get("/filters/counts")
async def get_filter_counts(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Dict[str, int]]:
    """
    Get filter values with their counts.

    This endpoint returns all distinct values for each attribute
    along with the count of products for each value.
    Useful for showing "(23)" next to filter options.

    Returns:
        Dictionary with counts for each filter value
    """
    try:
        # Get jewel types with counts
        jewel_types_result = await db.execute(
            select(Jewel.jewel_type, func.count(Jewel.id))
            .where(Jewel.jewel_type.isnot(None))
            .group_by(Jewel.jewel_type)
            .order_by(Jewel.jewel_type)
        )
        jewel_types = {row[0]: row[1] for row in jewel_types_result.fetchall()}

        # Get metals with counts
        metals_result = await db.execute(
            select(Jewel.metal, func.count(Jewel.id))
            .where(Jewel.metal.isnot(None))
            .group_by(Jewel.metal)
            .order_by(Jewel.metal)
        )
        metals = {row[0]: row[1] for row in metals_result.fetchall()}

        # Get gemstones with counts
        gemstones_result = await db.execute(
            select(Jewel.gemstone, func.count(Jewel.id))
            .where(Jewel.gemstone.isnot(None))
            .group_by(Jewel.gemstone)
            .order_by(Jewel.gemstone)
        )
        gemstones = {row[0]: row[1] for row in gemstones_result.fetchall()}

        # Get vibes with counts
        vibes_result = await db.execute(
            select(Jewel.vibe, func.count(Jewel.id))
            .where(Jewel.vibe.isnot(None))
            .group_by(Jewel.vibe)
            .order_by(Jewel.vibe)
        )
        vibes = {row[0]: row[1] for row in vibes_result.fetchall()}

        # Get metal colors with counts
        metal_colors_result = await db.execute(
            select(Jewel.metal_color, func.count(Jewel.id))
            .where(Jewel.metal_color.isnot(None))
            .group_by(Jewel.metal_color)
            .order_by(Jewel.metal_color)
        )
        metal_colors = {row[0]: row[1] for row in metal_colors_result.fetchall()}

        logger.info("Retrieved filter counts")

        return {
            "jewel_types": jewel_types,
            "metals": metals,
            "gemstones": gemstones,
            "vibes": vibes,
            "metal_colors": metal_colors
        }

    except Exception as e:
        logger.error(f"Error retrieving filter counts: {str(e)}")
        return {
            "jewel_types": {},
            "metals": {},
            "gemstones": {},
            "vibes": {},
            "metal_colors": {}
        }
