from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.database import get_db
from app.models.job import Job
from app.schemas.job import JobStatusResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the status of a scraping job by its ID.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        url=job.url,
        status=job.status,
        started_at=job.started_at,
        finished_at=job.finished_at,
        stats_json=job.stats_json,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at
    )
