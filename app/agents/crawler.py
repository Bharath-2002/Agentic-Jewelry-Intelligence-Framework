import asyncio
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CrawlerAgent:
    """Agent responsible for crawling websites and discovering product pages."""

    def __init__(self):
        self.settings = settings
        self.visited_urls = set()
        self.product_urls = []

    async def crawl(self, base_url: str, max_pages: Optional[int] = None) -> List[Dict]:
        """
        Crawl a website to discover and scrape product pages.

        Args:
            base_url: The starting URL to crawl
            max_pages: Maximum number of pages to crawl (default from settings)

        Returns:
            List of product data dictionaries
        """
        max_pages = max_pages or self.settings.crawler_max_pages
        logger.info(f"Starting crawl of {base_url} (max pages: {max_pages})")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.settings.crawler_headless
            )

            try:
                products = await self._crawl_with_browser(browser, base_url, max_pages)
                logger.info(f"Crawl completed. Found {len(products)} products.")
                return products
            finally:
                await browser.close()

    async def _crawl_with_browser(
        self, browser: Browser, base_url: str, max_pages: int
    ) -> List[Dict]:
        """Internal method to crawl with an active browser instance."""
        products = []
        to_visit = [base_url]
        domain = urlparse(base_url).netloc

        while to_visit and len(self.visited_urls) < max_pages:
            url = to_visit.pop(0)

            if url in self.visited_urls:
                continue

            try:
                logger.info(f"Crawling: {url}")
                self.visited_urls.add(url)

                page = await browser.new_page(
                    user_agent=self.settings.crawler_user_agent
                )

                try:
                    await page.goto(url, timeout=self.settings.crawler_timeout, wait_until="networkidle")

                    # Scroll to load lazy-loaded content
                    await self._scroll_page(page)

                    # Get page content
                    content = await page.content()

                    # Check if this is a product page
                    if await self._is_product_page(page, content):
                        logger.info(f"Found product page: {url}")
                        product_data = await self._extract_product_data(page, content, url)
                        products.append(product_data)
                    else:
                        # Extract links to potentially more pages
                        links = await self._extract_links(page, url, domain)
                        to_visit.extend(links)

                finally:
                    await page.close()

            except Exception as e:
                logger.error(f"Error crawling {url}: {str(e)}")
                continue

        return products

    async def _scroll_page(self, page: Page) -> None:
        """Scroll page to trigger lazy loading."""
        try:
            await page.evaluate("""
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 100;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if(totalHeight >= scrollHeight){
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                }
            """)
        except Exception as e:
            logger.warning(f"Error scrolling page: {str(e)}")

    async def _is_product_page(self, page: Page, content: str) -> bool:
        """Determine if a page is a product page."""
        soup = BeautifulSoup(content, 'lxml')

        # Check for common product page indicators
        indicators = [
            # Schema.org Product markup
            soup.find(attrs={"itemtype": lambda x: x and "Product" in x}),
            # Common product selectors
            soup.find(attrs={"class": lambda x: x and any(
                keyword in str(x).lower() for keyword in ["product", "item-detail", "pdp"]
            )}),
            # Price indicators
            soup.find(attrs={"class": lambda x: x and "price" in str(x).lower()}),
            # Add to cart buttons
            soup.find(text=lambda x: x and any(
                phrase in str(x).lower() for phrase in ["add to cart", "buy now", "add to bag"]
            ))
        ]

        return any(indicators)

    async def _extract_product_data(self, page: Page, content: str, url: str) -> Dict:
        """Extract raw product data from a product page."""
        soup = BeautifulSoup(content, 'lxml')

        # Extract images
        images = await self._extract_images(page, soup)

        # Extract basic HTML structure for later processing
        product_data = {
            "url": url,
            "html": content,
            "images": images,
            "title": await page.title(),
        }

        return product_data

    async def _extract_images(self, page: Page, soup: BeautifulSoup) -> List[str]:
        """Extract product images from the page."""
        images = []

        # Try to find product images
        img_selectors = [
            "img[class*='product']",
            "img[class*='gallery']",
            "img[itemprop='image']",
            ".product-image img",
            ".product-gallery img",
        ]

        for selector in img_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements[:self.settings.max_images_per_product]:
                    src = await element.get_attribute("src")
                    if src and not src.startswith("data:"):
                        # Convert relative URLs to absolute
                        absolute_url = urljoin(page.url, src)
                        images.append(absolute_url)

                if images:
                    break
            except Exception as e:
                logger.debug(f"Error extracting images with selector {selector}: {str(e)}")
                continue

        return images[:self.settings.max_images_per_product]

    async def _extract_links(self, page: Page, current_url: str, domain: str) -> List[str]:
        """Extract relevant links from the page."""
        links = []

        try:
            # Get all links
            link_elements = await page.query_selector_all("a[href]")

            for element in link_elements:
                href = await element.get_attribute("href")
                if not href:
                    continue

                # Convert to absolute URL
                absolute_url = urljoin(current_url, href)
                parsed = urlparse(absolute_url)

                # Only include links from the same domain
                if parsed.netloc != domain:
                    continue

                # Remove fragments and queries for deduplication
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

                # Look for product-like URLs
                if any(keyword in clean_url.lower() for keyword in [
                    "/product", "/item", "/p/", "/jewelry", "/ring", "/necklace",
                    "/bracelet", "/earring", "/pendant"
                ]):
                    if clean_url not in self.visited_urls:
                        links.append(clean_url)

        except Exception as e:
            logger.error(f"Error extracting links: {str(e)}")

        return links
