from typing import Optional
from sqlalchemy import String, Numeric, Text, Index
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDMixin


class Jewel(Base, UUIDMixin, TimestampMixin):
    """Jewel model for storing jewelry product data."""

    __tablename__ = "jewels"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Basic attributes
    jewel_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    metal: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    gemstone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gemstone_color: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metal_color: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Price information
    price_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    price_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # AI-inferred attributes
    inferred_attributes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # AI-generated content
    vibe: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Images and raw data
    images: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    raw_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    __table_args__ = (
        Index('idx_jewel_type_metal_vibe', 'jewel_type', 'metal', 'vibe'),
    )

    def __repr__(self) -> str:
        return f"<Jewel(id={self.id}, name={self.name}, jewel_type={self.jewel_type})>"
