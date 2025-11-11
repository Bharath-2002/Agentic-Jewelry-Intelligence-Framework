from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, HttpUrl, Field
from app.models.job import JobStatus


class JobCreate(BaseModel):
    """Schema for creating a new scraping job."""
    url: str = Field(..., description="URL to scrape")


class JobResponse(BaseModel):
    """Schema for job creation response."""
    job_id: UUID
    status: JobStatus

    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    """Schema for job status response."""
    job_id: UUID
    url: str
    status: JobStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    stats_json: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
