import logging
import asyncio
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.job import Job, JobStatus
from app.agents.crawler import IntelligentCrawler
from app.agents.extractor import ExtractorAgent
from app.agents.normalizer import NormalizerAgent
from app.agents.inference import InferenceAgent
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
    2-6. Product Pipeline (concurrent processing):
        - Extractor Agent - extracts metadata from HTML
        - Normalizer Agent - normalizes data to canonical format
        - Inference Agent - infers visual attributes, summary, and vibes using AI (combined)
        - Storage Agent - stores data with deduplication

    Performance optimizations:
    - Combined AI inference for attributes + summary/vibe (1 LLM call instead of 2)
    - Concurrent processing of multiple products (default: 3 products in parallel)
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
            crawler = IntelligentCrawler(settings)
            extractor = ExtractorAgent()
            normalizer = NormalizerAgent()
            inference = InferenceAgent()
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
            if max_products and max_products > 0:
                logger.info(
                    f"ℹ️  COST CONTROL: Will stop after storing {max_products} products in database. "
                    f"Set MAX_PRODUCTS_TO_PROCESS=0 in .env to disable this limit."
                )

            # Configure concurrent processing
            max_concurrent_products = getattr(settings, 'max_concurrent_products', 3)
            logger.info(f"⚡ Processing {max_concurrent_products} products concurrently")

            # Semaphore to limit concurrent processing
            semaphore = asyncio.Semaphore(max_concurrent_products)
            lock = asyncio.Lock()

            # Worker function to process a single product
            async def process_product(idx: int, product_data: dict):
                """Process a single product through the pipeline."""
                async with semaphore:
                    # Check max products limit (thread-safe)
                    async with lock:
                        if max_products and max_products > 0 and stats["products_stored"] >= max_products:
                            return None

                    try:
                        product_url = product_data.get("url")
                        logger.info(f"Processing product {idx + 1}/{len(products)}: {product_url}")

                        # Step 2: Extract metadata
                        logger.info(f"  [{idx + 1}] Step 2: Extracting metadata...")
                        extracted_data = extractor.extract(product_data)

                        # Step 3: Normalize data
                        logger.info(f"  [{idx + 1}] Step 3: Normalizing data...")
                        normalized_data = normalizer.normalize(extracted_data)

                        # Step 4 & 5 (Combined): Infer visual attributes + Generate summary/vibe with AI
                        logger.info(f"  [{idx + 1}] Step 4-5: Inferring attributes and generating summary...")
                        images = product_data.get("images", [])
                        inferred_data = await inference.infer_attributes(images, extracted_data)

                        # Check if product should be skipped (returns None if invalid)
                        if inferred_data is None:
                            logger.info(f"  [{idx + 1}] ⊘ Skipped (not a specific product): {product_url}")
                            return None

                        # Extract summary and vibe from inferred_data (now included in inference response)
                        summary_data = {
                            "summary": inferred_data.get("summary"),
                            "vibe": inferred_data.get("vibe")
                        }

                        # Step 6: Store in database
                        logger.info(f"  [{idx + 1}] Step 6: Storing in database...")
                        jewel = await storage.store_jewel(
                            db=db,
                            source_url=product_url,
                            images=images,
                            normalized_data=normalized_data,
                            inferred_data=inferred_data,
                            summary_data=summary_data
                        )

                        if jewel:
                            async with lock:
                                stats["products_stored"] += 1
                                stats["images_downloaded"] += len(jewel.images or [])
                            logger.info(f"  [{idx + 1}] ✓ Successfully stored: {jewel.name}")
                            return jewel
                        else:
                            logger.info(f"  [{idx + 1}] ⊘ Skipped (duplicate): {product_url}")
                            return None

                    except Exception as e:
                        logger.error(f"  [{idx + 1}] ✗ Error processing product: {str(e)}")
                        async with lock:
                            stats["errors"] += 1
                        return None

            # Process products concurrently in batches
            tasks = []
            for idx, product_data in enumerate(products):
                # Check if we've reached the limit before creating more tasks
                if max_products and max_products > 0 and stats["products_stored"] >= max_products:
                    logger.warning(
                        f"⚠️  COST CONTROL: Reached limit of {max_products} products stored in database. "
                        f"Stopping processing. Found {len(products)} total products, "
                        f"processed {idx} products, stored {stats['products_stored']} products."
                    )
                    break

                tasks.append(process_product(idx, product_data))

            # Wait for all products to be processed
            logger.info(f"Processing {len(tasks)} products concurrently...")
            await asyncio.gather(*tasks, return_exceptions=True)

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
