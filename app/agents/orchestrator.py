import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.job import Job, JobStatus
from app.agents.crawler import CrawlerAgent
from app.agents.extractor import ExtractorAgent
from app.agents.normalizer import NormalizerAgent
from app.agents.inference import InferenceAgent
from app.agents.summarizer import SummarizerAgent
from app.agents.storage import StorageAgent
from app.utils.email import send_job_notification
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def run_scraping_pipeline(job_id: str, url: str) -> None:
    """
    Main orchestration function that coordinates all agents in the scraping pipeline.

    Args:
        job_id: ID of the job to track
        url: URL to scrape

    This function runs as a background task and coordinates:
    1. Crawler Agent - discovers and scrapes product pages
    2. Extractor Agent - extracts metadata from HTML
    3. Normalizer Agent - normalizes data to canonical format
    4. Inference Agent - infers visual attributes using AI
    5. Summarizer Agent - generates summaries and vibes
    6. Storage Agent - stores data with deduplication
    """
    async with AsyncSessionLocal() as db:
        try:
            # Update job status to running
            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()

            if not job:
                logger.error(f"Job {job_id} not found")
                return

            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            await db.commit()

            logger.info(f"Starting scraping pipeline for job {job_id} - URL: {url}")

            # Initialize stats
            stats = {
                "pages_crawled": 0,
                "products_found": 0,
                "products_stored": 0,
                "images_downloaded": 0,
                "errors": 0
            }

            # Initialize agents
            crawler = CrawlerAgent()
            extractor = ExtractorAgent()
            normalizer = NormalizerAgent()
            inference = InferenceAgent()
            summarizer = SummarizerAgent()
            storage = StorageAgent()

            # Step 1: Crawl website for products
            logger.info("Step 1: Crawling website...")
            products = await crawler.crawl(url)
            stats["pages_crawled"] = len(crawler.visited_urls)
            stats["products_found"] = len(products)

            logger.info(f"Found {len(products)} products across {stats['pages_crawled']} pages")

            # Apply product limit for cost control (DEV/TESTING ONLY)
            # For production, set MAX_PRODUCTS_TO_PROCESS=0 or None in .env
            max_products = settings.max_products_to_process
            if max_products and max_products > 0 and len(products) > max_products:
                logger.warning(
                    f"⚠️  COST CONTROL: Limiting processing to {max_products} products "
                    f"(found {len(products)}). Set MAX_PRODUCTS_TO_PROCESS=0 in .env to disable this limit."
                )
                products = products[:max_products]
                stats["products_found"] = len(products)

            # Process each product through the pipeline
            for idx, product_data in enumerate(products):
                try:
                    product_url = product_data.get("url")
                    logger.info(f"Processing product {idx + 1}/{len(products)}: {product_url}")

                    # Step 2: Extract metadata
                    logger.info("  Step 2: Extracting metadata...")
                    extracted_data = extractor.extract(product_data)

                    # Step 3: Normalize data
                    logger.info("  Step 3: Normalizing data...")
                    normalized_data = normalizer.normalize(extracted_data)

                    # Step 4: Infer visual attributes with AI
                    logger.info("  Step 4: Inferring visual attributes...")
                    images = product_data.get("images", [])
                    inferred_data = await inference.infer_attributes(images, extracted_data)

                    # Step 5: Generate summary and vibe
                    logger.info("  Step 5: Generating summary and vibe...")
                    summary_data = await summarizer.generate_summary_and_vibe(
                        normalized_data,
                        inferred_data
                    )

                    # Step 6: Store in database
                    logger.info("  Step 6: Storing in database...")
                    jewel = await storage.store_jewel(
                        db=db,
                        source_url=product_url,
                        images=images,
                        normalized_data=normalized_data,
                        inferred_data=inferred_data,
                        summary_data=summary_data
                    )

                    if jewel:
                        stats["products_stored"] += 1
                        stats["images_downloaded"] += len(jewel.images or [])
                        logger.info(f"  ✓ Successfully stored: {jewel.name}")
                    else:
                        logger.info(f"  ⊘ Skipped (duplicate): {product_url}")

                except Exception as e:
                    logger.error(f"  ✗ Error processing product: {str(e)}")
                    stats["errors"] += 1
                    continue

            # Update job status to success
            job.status = JobStatus.SUCCESS
            job.finished_at = datetime.utcnow()
            job.stats_json = stats
            await db.commit()

            logger.info(f"Pipeline completed successfully for job {job_id}")
            logger.info(f"Stats: {stats}")

            # Send success email notification
            await send_job_notification(
                job_id=job_id,
                job_url=url,
                status="success",
                stats=stats,
                started_at=job.started_at,
                finished_at=job.finished_at
            )

        except Exception as e:
            logger.error(f"Pipeline failed for job {job_id}: {str(e)}")

            # Update job status to failed
            try:
                result = await db.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()
                if job:
                    job.status = JobStatus.FAILED
                    job.finished_at = datetime.utcnow()
                    job.error_message = str(e)
                    job.stats_json = stats
                    await db.commit()

                    # Send failure email notification
                    await send_job_notification(
                        job_id=job_id,
                        job_url=url,
                        status="failed",
                        stats=stats,
                        error_message=str(e),
                        started_at=job.started_at,
                        finished_at=job.finished_at
                    )
            except Exception as update_error:
                logger.error(f"Failed to update job status: {str(update_error)}")
