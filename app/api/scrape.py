from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from app.database import get_db
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate, JobResponse
from app.agents.orchestrator import run_scraping_pipeline
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/scrape", response_model=JobResponse)
async def create_scrape_job(
    job_data: JobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new scraping job for the given URL.
    The job will be processed in the background.
    """
    # Create job record
    job = Job(
        url=job_data.url,
        status=JobStatus.QUEUED,
        stats_json={}
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Add background task
    background_tasks.add_task(run_scraping_pipeline, str(job.id), job_data.url)

    logger.info(f"Created scraping job {job.id} for URL: {job_data.url}")

    return JobResponse(
        job_id=job.id,
        status=job.status
    )
