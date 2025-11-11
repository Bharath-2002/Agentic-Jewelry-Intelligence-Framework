from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import String, DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDMixin


class JobStatus(str, PyEnum):
    """Job status enumeration."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Job(Base, UUIDMixin, TimestampMixin):
    """Job model for tracking scraping tasks."""

    __tablename__ = "jobs"

    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=JobStatus.QUEUED,
        nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stats_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, url={self.url}, status={self.status})>"
