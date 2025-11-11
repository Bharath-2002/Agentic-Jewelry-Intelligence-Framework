import logging
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import aiofiles
from app.models.jewel import Jewel
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class StorageAgent:
    """Agent responsible for storing jewelry data and images."""

    def __init__(self):
        self.settings = settings
        self.image_storage_path = Path(settings.image_storage_path)
        self.image_storage_path.mkdir(parents=True, exist_ok=True)

    async def store_jewel(
        self,
        db: AsyncSession,
        source_url: str,
        images: List[str],
        normalized_data: Dict[str, Any],
        inferred_data: Dict[str, Any],
        summary_data: Dict[str, str]
    ) -> Optional[Jewel]:
        """
        Store a jewelry item in the database with deduplication.

        Args:
            db: Database session
            source_url: Original product URL
            images: List of image URLs
            normalized_data: Normalized product data
            inferred_data: AI-inferred attributes
            summary_data: Summary and vibe data

        Returns:
            Jewel model instance or None if duplicate
        """
        # Check for duplicates
        if await self._is_duplicate(db, source_url):
            logger.info(f"Duplicate detected for URL: {source_url}")
            return None

        try:
            # Download and store images
            stored_images = await self._download_images(images, source_url)

            # Merge inferred attributes into normalized data
            merged_data = self._merge_attributes(normalized_data, inferred_data)

            # Create Jewel instance
            jewel = Jewel(
                name=merged_data.get("name", "Unknown Product"),
                source_url=source_url,
                jewel_type=merged_data.get("jewel_type"),
                metal=merged_data.get("metal"),
                gemstone=merged_data.get("gemstone"),
                gemstone_color=merged_data.get("gemstone_color"),
                metal_color=merged_data.get("metal_color"),
                color=merged_data.get("color"),
                price_amount=merged_data.get("price_amount"),
                price_currency=merged_data.get("price_currency"),
                inferred_attributes=inferred_data,
                vibe=summary_data.get("vibe"),
                summary=summary_data.get("summary"),
                images=stored_images,
                raw_metadata=merged_data.get("raw_metadata", {})
            )

            db.add(jewel)
            await db.commit()
            await db.refresh(jewel)

            logger.info(f"Successfully stored jewel: {jewel.name} (ID: {jewel.id})")
            return jewel

        except Exception as e:
            logger.error(f"Error storing jewel: {str(e)}")
            await db.rollback()
            return None

    async def _is_duplicate(self, db: AsyncSession, source_url: str) -> bool:
        """
        Check if a product already exists in the database.

        Args:
            db: Database session
            source_url: Product URL to check

        Returns:
            True if duplicate exists, False otherwise
        """
        result = await db.execute(
            select(Jewel).where(Jewel.source_url == source_url)
        )
        existing = result.scalar_one_or_none()
        return existing is not None

    def _merge_attributes(
        self,
        normalized_data: Dict[str, Any],
        inferred_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge normalized and inferred data, preferring inferred values when available.

        Args:
            normalized_data: Normalized extracted data
            inferred_data: AI-inferred attributes

        Returns:
            Merged dictionary
        """
        merged = normalized_data.copy()

        # Update with inferred values if they exist and have good confidence
        if inferred_data.get("jewelry_type"):
            merged["jewel_type"] = inferred_data["jewelry_type"]

        if inferred_data.get("gemstone"):
            merged["gemstone"] = inferred_data["gemstone"]

        if inferred_data.get("gemstone_color"):
            merged["gemstone_color"] = inferred_data["gemstone_color"]

        if inferred_data.get("metal_color"):
            merged["metal_color"] = inferred_data["metal_color"]

        return merged

    async def _download_images(
        self,
        image_urls: List[str],
        source_url: str
    ) -> List[str]:
        """
        Download images and store them locally.

        Args:
            image_urls: List of image URLs to download
            source_url: Product URL (used for generating unique filenames)

        Returns:
            List of local file paths
        """
        stored_paths = []

        # Create a hash of the source URL for unique directory
        url_hash = hashlib.md5(source_url.encode()).hexdigest()[:16]
        product_dir = self.image_storage_path / url_hash
        product_dir.mkdir(exist_ok=True)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for idx, image_url in enumerate(image_urls[:self.settings.max_images_per_product]):
                try:
                    logger.info(f"Downloading image: {image_url}")

                    # Download image
                    response = await client.get(image_url)
                    response.raise_for_status()

                    # Determine file extension
                    content_type = response.headers.get("content-type", "")
                    ext = self._get_extension_from_content_type(content_type) or ".jpg"

                    # Save to file
                    filename = f"image_{idx}{ext}"
                    filepath = product_dir / filename
                    relative_path = str(filepath.relative_to(self.image_storage_path))

                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(response.content)

                    stored_paths.append(relative_path)
                    logger.info(f"Saved image to: {relative_path}")

                except Exception as e:
                    logger.error(f"Error downloading image {image_url}: {str(e)}")
                    continue

        return stored_paths

    def _get_extension_from_content_type(self, content_type: str) -> Optional[str]:
        """Get file extension from content type."""
        content_type_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }
        return content_type_map.get(content_type.lower())

    def _calculate_image_hash(self, image_data: bytes) -> str:
        """Calculate hash of image data for deduplication."""
        return hashlib.md5(image_data).hexdigest()
