#!/usr/bin/env python3
"""
Example usage script demonstrating the Agentic Jewelry Intelligence API.

This script shows how to:
1. Create a scraping job
2. Monitor job progress
3. Query the results
"""

import httpx
import asyncio
import time
from typing import Dict, Optional


API_BASE_URL = "http://localhost:8000"


async def create_scraping_job(url: str) -> Dict:
    """Create a new scraping job."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/scrape",
            json={"url": url}
        )
        response.raise_for_status()
        return response.json()


async def get_job_status(job_id: str) -> Dict:
    """Get the status of a scraping job."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/status/{job_id}")
        response.raise_for_status()
        return response.json()


async def list_jewels(
    limit: int = 10,
    vibe: Optional[str] = None,
    metal: Optional[str] = None,
    jewel_type: Optional[str] = None
) -> Dict:
    """List jewelry products with optional filters."""
    params = {"limit": limit}
    if vibe:
        params["vibe"] = vibe
    if metal:
        params["metal"] = metal
    if jewel_type:
        params["jewel_type"] = jewel_type

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/jewels", params=params)
        response.raise_for_status()
        return response.json()


async def wait_for_job_completion(job_id: str, max_wait: int = 300) -> Dict:
    """Wait for a job to complete (max 5 minutes by default)."""
    start_time = time.time()

    while time.time() - start_time < max_wait:
        status_data = await get_job_status(job_id)
        status = status_data["status"]

        print(f"Job status: {status}")

        if status == "success":
            print("✓ Job completed successfully!")
            return status_data
        elif status == "failed":
            print("✗ Job failed!")
            print(f"Error: {status_data.get('error_message')}")
            return status_data

        # Wait 5 seconds before checking again
        await asyncio.sleep(5)

    print("⚠ Job is still running after max wait time")
    return status_data


async def main():
    """Main demonstration function."""
    print("=" * 70)
    print("Agentic Jewelry Intelligence Framework - Example Usage")
    print("=" * 70)
    print()

    # Example 1: Create a scraping job
    print("Example 1: Creating a scraping job")
    print("-" * 70)

    # Note: Replace with an actual jewelry website URL
    test_url = "https://www.example-jewelry-site.com"

    print(f"Creating scraping job for: {test_url}")
    try:
        job_data = await create_scraping_job(test_url)
        job_id = job_data["job_id"]
        print(f"✓ Job created with ID: {job_id}")
        print(f"  Status: {job_data['status']}")
    except httpx.HTTPError as e:
        print(f"✗ Error creating job: {e}")
        print("\nMake sure the API server is running:")
        print("  docker-compose up")
        print("  or")
        print("  poetry run python run.py dev")
        return

    print()

    # Example 2: Monitor job progress
    print("Example 2: Monitoring job progress")
    print("-" * 70)

    print("Waiting for job to complete...")
    final_status = await wait_for_job_completion(job_id, max_wait=120)

    if final_status["status"] == "success":
        stats = final_status.get("stats_json", {})
        print(f"\nJob Statistics:")
        print(f"  Pages crawled: {stats.get('pages_crawled', 0)}")
        print(f"  Products found: {stats.get('products_found', 0)}")
        print(f"  Products stored: {stats.get('products_stored', 0)}")
        print(f"  Images downloaded: {stats.get('images_downloaded', 0)}")
        print(f"  Errors: {stats.get('errors', 0)}")

    print()

    # Example 3: Query jewelry products
    print("Example 3: Querying jewelry products")
    print("-" * 70)

    print("Fetching all jewelry (limit 5)...")
    try:
        jewels_data = await list_jewels(limit=5)
        print(f"✓ Found {jewels_data['total']} total products")
        print(f"  Showing {len(jewels_data['items'])} items:\n")

        for i, jewel in enumerate(jewels_data["items"], 1):
            print(f"  {i}. {jewel['name']}")
            print(f"     Type: {jewel.get('jewel_type', 'N/A')}")
            print(f"     Metal: {jewel.get('metal', 'N/A')}")
            print(f"     Gemstone: {jewel.get('gemstone', 'N/A')}")
            print(f"     Vibe: {jewel.get('vibe', 'N/A')}")
            if jewel.get('price_amount'):
                print(f"     Price: {jewel['price_currency']} {jewel['price_amount']}")
            print(f"     Summary: {jewel.get('summary', 'N/A')[:80]}...")
            print()

    except httpx.HTTPError as e:
        print(f"✗ Error querying jewels: {e}")

    print()

    # Example 4: Filtered queries
    print("Example 4: Filtered queries")
    print("-" * 70)

    # Query by vibe
    print("Querying wedding jewelry...")
    try:
        wedding_jewels = await list_jewels(vibe="wedding", limit=3)
        print(f"✓ Found {wedding_jewels['total']} wedding items")
    except httpx.HTTPError as e:
        print(f"✗ Error: {e}")

    print()

    # Query by metal
    print("Querying gold jewelry...")
    try:
        gold_jewels = await list_jewels(metal="gold", limit=3)
        print(f"✓ Found {gold_jewels['total']} gold items")
    except httpx.HTTPError as e:
        print(f"✗ Error: {e}")

    print()

    # Combined filters
    print("Querying engagement rings in platinum...")
    try:
        engagement_rings = await list_jewels(
            vibe="engagement",
            metal="platinum",
            jewel_type="ring",
            limit=3
        )
        print(f"✓ Found {engagement_rings['total']} matching items")
    except httpx.HTTPError as e:
        print(f"✗ Error: {e}")

    print()
    print("=" * 70)
    print("Example usage complete!")
    print()
    print("Next steps:")
    print("  1. Visit http://localhost:8000/docs for interactive API docs")
    print("  2. Try different filter combinations")
    print("  3. Scrape your favorite jewelry website")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
