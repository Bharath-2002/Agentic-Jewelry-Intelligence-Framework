import asyncio
import logging
from typing import List, Dict, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup
import re
import json
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import openai
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class PageType(Enum):
    """Classification of page types"""
    PRODUCT = "product"
    CATEGORY = "category"
    LISTING = "listing"
    HOME = "home"
    OTHER = "other"


@dataclass
class CrawlStrategy:
    """Configuration for different crawling strategies"""
    name: str
    priority: int
    enabled: bool = True


@dataclass
class SitePattern:
    """Learned patterns about the website structure"""
    product_url_patterns: List[str] = field(default_factory=list)
    product_link_selectors: List[str] = field(default_factory=list)
    category_selectors: List[str] = field(default_factory=list)
    pagination_selectors: List[str] = field(default_factory=list)
    product_indicators: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


class IntelligentCrawler:
    """
    Enhanced crawler with multiple advanced strategies:
    1. LLM-powered page analysis
    2. Adaptive pattern learning
    3. Visual structure analysis
    4. Multiple fallback strategies
    5. Smart link extraction
    """

    def __init__(self, settings):
        self.settings = settings
        self.visited_urls: Set[str] = set()
        self.product_urls: Set[str] = set()
        self.category_urls: Set[str] = set()
        self.site_patterns = SitePattern()
        openai_api_key = settings.openai_api_key
        self.openai_client = None

        # Concurrency control
        self.max_concurrent_pages = getattr(settings, 'crawler_concurrent_pages', 5)
        self.lock = asyncio.Lock()  # For thread-safe operations on shared state

        if openai_api_key:
            self.openai_client = openai.OpenAI(api_key=openai_api_key)
            logger.info("🤖 LLM integration enabled")

        logger.info(f"⚡ Concurrent crawling enabled: {self.max_concurrent_pages} pages in parallel")
        
    async def crawl(self, base_url: str, max_pages: Optional[int] = None) -> List[Dict]:
        """Main crawl orchestration with multiple strategies"""
        max_pages = max_pages or self.settings.crawler_max_pages
        logger.info(f"🚀 Starting enhanced intelligent crawl of {base_url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.settings.crawler_headless
            )
            
            try:
                # Strategy 1: Try sitemap first (most efficient)
                await self._crawl_sitemap(browser, base_url)
                
                # Strategy 2: Analyze homepage to learn structure
                await self._analyze_homepage(browser, base_url)
                
                # Strategy 3: Intelligent crawl with learned patterns
                products = await self._intelligent_crawl(browser, base_url, max_pages)
                
                logger.info(f"✅ Crawl completed. Found {len(products)} products from {len(self.visited_urls)} pages")
                logger.info(f"📊 Learned patterns: {len(self.site_patterns.product_url_patterns)} URL patterns, "
                          f"{len(self.site_patterns.product_link_selectors)} link selectors products are {products}")
                
                return products
                
            finally:
                await browser.close()

    async def _crawl_sitemap(self, browser: Browser, base_url: str) -> None:
        """Strategy 1: Parse sitemap.xml for product URLs"""
        sitemap_urls = [
            urljoin(base_url, '/sitemap.xml'),
            urljoin(base_url, '/sitemap_index.xml'),
            urljoin(base_url, '/product-sitemap.xml'),
            urljoin(base_url, '/sitemap_products.xml'),
            urljoin(base_url, '/sitemap-products.xml'),
            urljoin(base_url, '/product_sitemap.xml'),
        ]
        
        page = await browser.new_page()
        try:
            for sitemap_url in sitemap_urls:
                try:
                    logger.info(f"🗺️  Checking sitemap: {sitemap_url}")
                    response = await page.goto(sitemap_url, timeout=10000, wait_until="domcontentloaded")
                    
                    if response and response.status == 200:
                        content = await page.content()
                        
                        # Parse sitemap XML
                        soup = BeautifulSoup(content, 'xml')
                        
                        # Find all URLs in sitemap
                        urls = soup.find_all('loc')
                        for url_tag in urls:
                            url = url_tag.get_text().strip()
                            
                            # Check if it's another sitemap
                            logger.info(f"🗺️  Checking sitemap in for : {url}")
                            if 'sitemap' in url.lower() and '.xml' in url.lower():
                                # Recursively check nested sitemap
                                logger.info(f"🗺️  Checking sitemap inside : {url}")
                                await self._crawl_nested_sitemap(page, url)
                            elif self._looks_like_product_url_sitemap(url):
                                self.product_urls.add(url)
                                logger.debug(f"Found product URL in sitemap: {url}")
                        
                        if len(self.product_urls) > 0:
                            logger.info(f"✅ Found {len(self.product_urls)} product URLs in sitemap")
                            return
                        
                except Exception as e:
                    logger.debug(f"Sitemap not available: {sitemap_url} - {str(e)}")
                    continue
                    
        finally:
            await page.close()

    async def  _crawl_nested_sitemap(self, page: Page, sitemap_url: str) -> None:
        """Recursively crawl nested sitemaps"""
        try:
            response = await page.goto(sitemap_url, timeout=10000, wait_until="domcontentloaded")
            if response and response.status == 200:
                content = await page.content()
                soup = BeautifulSoup(content, 'xml')
                
                urls = soup.find_all('loc')
                for url_tag in urls:
                    url = url_tag.get_text().strip()
                    if self._looks_like_product_url_sitemap(url):
                        self.product_urls.add(url)
        except Exception as e:
            logger.debug(f"Error crawling nested sitemap {sitemap_url}: {str(e)}")

    async def _analyze_homepage(self, browser: Browser, base_url: str) -> None:
        """Analyze homepage to learn site structure"""
        logger.info("🔬 Analyzing homepage structure...")
        
        page = await browser.new_page(user_agent=self.settings.crawler_user_agent)
        try:
            await page.goto(base_url, timeout=self.settings.crawler_timeout, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            await self._scroll_page(page)
            
            content = await page.content()
            soup = BeautifulSoup(content, 'lxml')
            
            # Extract navigation and main links
            nav_links = await self._extract_navigation_links(page, soup, base_url)
            
            # Use LLM to analyze page structure if available
            if self.openai_client:
                await self._llm_analyze_page_structure(content, base_url, nav_links)
            
            # Learn common patterns from homepage
            await self._learn_from_page(page, soup, base_url)
            
        except Exception as e:
            logger.error(f"Error analyzing homepage: {str(e)}")
        finally:
            await page.close()

    async def _extract_navigation_links(self, page: Page, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract navigation menu links (likely category pages)"""
        nav_links = set()
        domain = urlparse(base_url).netloc
        
        # Navigation selectors
        nav_selectors = [
            "nav a[href]",
            "header a[href]",
            "[class*='nav'] a[href]",
            "[class*='menu'] a[href]",
            "[id*='nav'] a[href]",
            "[id*='menu'] a[href]",
        ]
        
        for selector in nav_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    href = await element.get_attribute("href")
                    text = await element.inner_text()
                    
                    if href and text:
                        absolute_url = urljoin(base_url, href)
                        if self._is_same_domain(absolute_url, domain):
                            # Likely category if text suggests it
                            if any(keyword in text.lower() for keyword in 
                                  ['shop', 'collection', 'category', 'product', 'ring', 'necklace', 
                                   'earring', 'bracelet', 'jewelry', 'jewellery']):
                                self.category_urls.add(self._clean_url(absolute_url))
                                nav_links.add(self._clean_url(absolute_url))
            except Exception as e:
                continue
        
        logger.info(f"📍 Found {len(nav_links)} navigation links")
        return list(nav_links)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _llm_analyze_page_structure(self, html: str, url: str, nav_links: List[str]) -> None:
        """Use LLM to analyze page structure and extract patterns"""
        if not self.openai_client:
            return
        
        try:
            # Simplified HTML for LLM analysis
            soup = BeautifulSoup(html, 'lxml')
            
            # Remove script and style tags
            for tag in soup(['script', 'style', 'svg']):
                tag.decompose()
            
            # Get simplified structure
            simplified_html = str(soup)[:15000]  # Limit size
            
            prompt = f"""Analyze this e-commerce website's HTML structure and identify patterns:

URL: {url}
Navigation Links Found: {json.dumps(nav_links[:10], indent=2)}

HTML Structure (truncated):
{simplified_html}

Please identify:
1. CSS selectors for product links (e.g., ".product-card a", "[data-product-id]")
2. URL patterns for products (e.g., /products/*, /p/*, /item/*)
3. CSS selectors for product grids/listings
4. Pagination patterns
5. Product page indicators (classes, attributes, text)

Respond in JSON format:
{{
    "product_link_selectors": ["selector1", "selector2"],
    "product_url_patterns": ["/pattern1/", "/pattern2/"],
    "listing_selectors": ["selector1", "selector2"],
    "pagination_selectors": ["selector1", "selector2"],
    "product_indicators": {{"class": "example", "text": "Add to Cart"}}
}}
"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Cheaper and faster model
                messages=[
                    {"role": "system", "content": "You are an expert in web scraping and HTML structure analysis. Provide only valid JSON responses."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            result = response.choices[0].message.content
            
            # Parse JSON response
            # Clean the response in case it has markdown code blocks
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.startswith("```"):
                result = result[3:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()
            
            patterns = json.loads(result)
            
            # Update site patterns
            self.site_patterns.product_link_selectors.extend(patterns.get("product_link_selectors", []))
            self.site_patterns.product_url_patterns.extend(patterns.get("product_url_patterns", []))
            self.site_patterns.category_selectors.extend(patterns.get("listing_selectors", []))
            self.site_patterns.pagination_selectors.extend(patterns.get("pagination_selectors", []))
            
            logger.info(f"🤖 LLM identified {len(patterns.get('product_link_selectors', []))} selectors")
            
        except Exception as e:
            logger.warning(f"LLM analysis failed: {str(e)}")

    async def _learn_from_page(self, page: Page, soup: BeautifulSoup, url: str) -> None:
        """Learn patterns from the current page"""
        # Learn link patterns
        all_links = await page.query_selector_all("a[href]")
        
        link_patterns = defaultdict(int)
        for link_elem in all_links[:100]:  # Sample first 100
            try:
                href = await link_elem.get_attribute("href")
                classes = await link_elem.get_attribute("class")
                
                if href and classes:
                    # Count class patterns that might indicate products
                    for cls in classes.split():
                        if any(keyword in cls.lower() for keyword in ['product', 'item', 'card']):
                            link_patterns[f".{cls} a"] += 1
            except:
                continue
        
        # Add high-frequency patterns
        for selector, count in sorted(link_patterns.items(), key=lambda x: -x[1])[:5]:
            if selector not in self.site_patterns.product_link_selectors:
                self.site_patterns.product_link_selectors.append(selector)

    async def _intelligent_crawl(self, browser: Browser, base_url: str, max_pages: int) -> List[Dict]:
        """Enhanced intelligent crawling with concurrent processing"""
        products = []
        domain = urlparse(base_url).netloc

        # Initialize queue with discovered categories
        priority_queue = self._initialize_enhanced_priority_queue(base_url)

        # Add sitemap products with highest priority
        if self.product_urls:
            for url in list(self.product_urls)[:max_pages]:
                if url not in self.visited_urls:
                    priority_queue.insert(0, (100, url, PageType.PRODUCT))

        # Create a semaphore to limit concurrent pages
        semaphore = asyncio.Semaphore(self.max_concurrent_pages)

        # Create worker tasks
        async def crawl_url(priority: int, url: str, expected_type: PageType):
            """Worker function to crawl a single URL"""
            async with semaphore:  # Limit concurrent pages
                # Check if already visited (thread-safe)
                async with self.lock:
                    if url in self.visited_urls or len(self.visited_urls) >= max_pages:
                        return None
                    if self._should_skip_url(url):
                        return None
                    self.visited_urls.add(url)
                    current_count = len(self.visited_urls)

                try:
                    logger.info(f"🔍 [{current_count}/{max_pages}] Crawling: {url} (priority: {priority}, type: {expected_type.value})")

                    page = await browser.new_page(user_agent=self.settings.crawler_user_agent)

                    try:
                        response = await page.goto(url, timeout=self.settings.crawler_timeout, wait_until="domcontentloaded")

                        # Check if page loaded successfully
                        if not response or response.status >= 400:
                            logger.warning(f"⚠️  Page returned status {response.status if response else 'unknown'}")
                            return None

                        # Wait for dynamic content
                        await asyncio.sleep(1.5)
                        await self._scroll_page(page)

                        content = await page.content()
                        soup = BeautifulSoup(content, 'lxml')

                        # Enhanced page classification
                        page_type = await self._enhanced_classify_page(page, soup, url)

                        result = {
                            'url': url,
                            'page_type': page_type,
                            'product_data': None,
                            'product_links': [],
                            'next_pages': [],
                            'other_links': []
                        }

                        if page_type == PageType.PRODUCT:
                            logger.info(f"✨ Found product page: {url}")
                            product_data = await self._extract_product_data(page, content, url)

                            # Validate it's actually a product
                            if self._validate_product_data(product_data):
                                result['product_data'] = product_data
                                self._learn_url_pattern(url)
                            else:
                                logger.warning(f"⚠️  Page classified as product but validation failed: {url}")
                                result['page_type'] = PageType.OTHER

                        if page_type in [PageType.CATEGORY, PageType.LISTING]:
                            logger.info(f"📁 Found {page_type.value} page: {url}")

                            # Multiple strategies to extract product links
                            product_links = await self._extract_product_links_multi_strategy(page, soup, url, domain)
                            result['product_links'] = product_links

                            # Handle pagination
                            next_pages = await self._find_pagination_multi_strategy(page, soup, url, domain)
                            result['next_pages'] = next_pages

                        else:
                            # Extract promising links
                            links = await self._extract_promising_links(page, soup, url, domain)
                            result['other_links'] = links[:20]  # Limit to top 20

                        return result

                    finally:
                        await page.close()

                except Exception as e:
                    logger.error(f"❌ Error crawling {url}: {str(e)}")
                    return None

        # Process URLs in batches
        while priority_queue and len(self.visited_urls) < max_pages:
            # Get next batch of URLs to process
            batch_size = min(self.max_concurrent_pages * 2, len(priority_queue), max_pages - len(self.visited_urls))

            if batch_size <= 0:
                break

            # Extract batch from queue
            batch = []
            for _ in range(batch_size):
                if priority_queue:
                    batch.append(priority_queue.pop(0))

            # Create tasks for concurrent execution
            tasks = [crawl_url(priority, url, expected_type) for priority, url, expected_type in batch]

            # Wait for all tasks in batch to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and update queue
            for result in results:
                if result is None or isinstance(result, Exception):
                    continue

                # Add product if found
                if result['product_data']:
                    async with self.lock:
                        products.append(result['product_data'])

                # Add discovered links to queue
                async with self.lock:
                    # Add product links with high priority
                    for link in result['product_links']:
                        if link not in self.visited_urls and link not in [item[1] for item in priority_queue]:
                            priority_queue.insert(0, (95, link, PageType.PRODUCT))

                    # Add pagination links
                    for next_url in result['next_pages']:
                        if next_url not in self.visited_urls and next_url not in [item[1] for item in priority_queue]:
                            priority_queue.insert(len(result['product_links']), (85, next_url, result['page_type']))

                    # Add other promising links
                    for link, link_priority in result['other_links']:
                        if link not in self.visited_urls and link not in [item[1] for item in priority_queue]:
                            priority_queue.append((link_priority, link, PageType.OTHER))

                    # Re-sort queue by priority
                    priority_queue.sort(key=lambda x: -x[0])

        return products

    def _initialize_enhanced_priority_queue(self, base_url: str) -> List[tuple]:
        """Initialize with discovered categories and common paths"""
        queue = []
        
        # Add discovered category URLs with high priority
        for cat_url in self.category_urls:
            queue.append((90, cat_url, PageType.CATEGORY))
        
        # Add homepage if no categories found
        if not queue:
            queue.append((85, base_url, PageType.HOME))
        
        # Add common paths (lower priority)
        common_paths = [
            '/shop', '/products', '/jewelry', '/jewellery', '/collection', '/collections',
            '/rings', '/necklaces', '/earrings', '/bracelets', '/pendants',
            '/categories', '/catalog', '/store',
            '/new-arrivals', '/new', '/best-sellers', '/featured'
        ]
        
        for path in common_paths:
            url = urljoin(base_url, path)
            if url not in [item[1] for item in queue]:
                queue.append((70, url, PageType.CATEGORY))
        
        return queue

    async def _enhanced_classify_page(self, page: Page, soup: BeautifulSoup, url: str) -> PageType:
        """Enhanced page classification with multiple signals"""
        
        # Quick rejection for obvious non-product pages
        if self._should_skip_url(url):
            return PageType.OTHER
        
        # Score-based classification
        product_score = 0
        category_score = 0
        
        # Signal 1: URL patterns (learned + common)
        url_lower = url.lower()
        product_url_keywords = ['/item/', '/p/', '/jewel/', '/jewelry-'] + \
                               [p.lower() for p in self.site_patterns.product_url_patterns]
        category_url_keywords = ['/category/', '/collection/', '/products', '/shop', '/catalog']
        
        if any(kw in url_lower for kw in product_url_keywords):
            product_score += 20
        if any(kw in url_lower for kw in category_url_keywords) and url_lower.count('/') <= 4:
            category_score += 20
        
        # Signal 2: Schema.org markup
        schema_types = soup.find_all(attrs={"itemtype": True})
        for schema in schema_types:
            itemtype = schema.get("itemtype", "")
            if "Product" in itemtype:
                product_score += 30
            elif any(x in itemtype for x in ["CollectionPage", "ItemList"]):
                category_score += 20
        
        # Signal 3: Strong product indicators
        # Price element
        if soup.find(attrs={"class": lambda x: x and "price" in str(x).lower()}):
            product_score += 10
        if soup.find(attrs={"itemprop": "price"}):
            product_score += 15
        
        # Add to cart
        if soup.find(text=re.compile(r'add to (cart|bag|basket)', re.I)):
            product_score += 15
        if soup.find(attrs={"class": lambda x: x and any(k in str(x).lower() for k in ['add-to-cart', 'add-cart', 'buy-now'])}):
            product_score += 15
        
        # Product title (single h1)
        h1_tags = soup.find_all("h1")
        if len(h1_tags) == 1:
            product_score += 10
        
        # Signal 4: Multiple product cards (category indicator)
        product_cards = await self._count_product_cards_enhanced(page, soup)
        if product_cards >= 6:
            category_score += 30
            product_score -= 20
        elif product_cards >= 3:
            category_score += 20
            product_score -= 10
        elif product_cards <= 1:
            product_score += 5
        
        # Signal 5: Filter/sort controls (category indicator)
        if soup.find(text=re.compile(r'sort by|filter|refine results', re.I)):
            category_score += 15
        if soup.find(attrs={"class": lambda x: x and any(k in str(x).lower() for k in ['filter', 'sort', 'refine'])}):
            category_score += 15
        
        # Signal 6: Image gallery (product indicator)
        img_count = len(soup.find_all('img', src=lambda x: x and not x.startswith('data:')))
        if 3 <= img_count <= 15:
            product_score += 5
        elif img_count > 15:
            category_score += 5
        
        # Signal 7: Breadcrumbs depth
        breadcrumbs = soup.find(attrs={"class": lambda x: x and "breadcrumb" in str(x).lower()})
        if breadcrumbs:
            links = breadcrumbs.find_all('a')
            if len(links) >= 3:  # Deep breadcrumbs suggest product
                product_score += 10
        
        logger.debug(f"Classification scores - Product: {product_score}, Category: {category_score}, URL: {url}")
        
        # Decision
        if "/product" in url_lower:
            return PageType.PRODUCT
        if product_score >= 40:
            return PageType.PRODUCT
        elif category_score >= 30:
            return PageType.CATEGORY if product_cards >= 10 else PageType.LISTING
        elif product_cards >= 3:
            return PageType.LISTING
        else:
            return PageType.OTHER

    async def _count_product_cards_enhanced(self, page: Page, soup: BeautifulSoup) -> int:
        """Enhanced product card counting with learned patterns"""
        max_count = 0
        
        # Use learned selectors
        for selector in self.site_patterns.product_link_selectors:
            try:
                elements = await page.query_selector_all(selector)
                count = len(elements)
                max_count = max(max_count, count)
            except:
                continue
        
        # Standard selectors
        card_selectors = [
            "[class*='product-card']", "[class*='product-item']", "[class*='product-tile']",
            "[class*='product-grid'] > *", "[class*='product-list'] > *",
            "[data-product-id]", "[data-product]", "[itemtype*='Product']",
            "[class*='product'] [class*='card']", "[class*='item-card']",
            "article[class*='product']", ".product", ".item-card",
        ]
        
        for selector in card_selectors:
            try:
                elements = await page.query_selector_all(selector)
                count = len(elements)
                max_count = max(max_count, count)
            except:
                continue
        
        return max_count

    async def _extract_product_links_multi_strategy(self, page: Page, soup: BeautifulSoup, 
                                                     current_url: str, domain: str) -> List[str]:
        """Extract product links using multiple strategies"""
        product_links = set()
        
        # Strategy 1: Use learned selectors
        for selector in self.site_patterns.product_link_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    href = await element.get_attribute("href")
                    if href:
                        absolute_url = urljoin(current_url, href)
                        if self._is_same_domain(absolute_url, domain) and self._looks_like_product_url(absolute_url):
                            product_links.add(self._clean_url(absolute_url))
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {str(e)}")
                continue
        
        # Strategy 2: Standard product card selectors
        card_selectors = [
            "[class*='product-card'] a[href]", "[class*='product-item'] a[href]",
            "[class*='product-tile'] a[href]", "[class*='product-grid'] a[href]",
            "[itemtype*='Product'] a[href]", "[data-product-id] a[href]",
            "article[class*='product'] a", ".product a[href]",
            "[class*='item-card'] a[href]", "[class*='product'] h2 a", "[class*='product'] h3 a",
        ]
        
        for selector in card_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    href = await element.get_attribute("href")
                    if href:
                        absolute_url = urljoin(current_url, href)
                        if self._is_same_domain(absolute_url, domain) and self._looks_like_product_url(absolute_url):
                            product_links.add(self._clean_url(absolute_url))
            except:
                continue
        
        # Strategy 3: Find all links and filter aggressively
        if len(product_links) < 5:
            all_links = await page.query_selector_all("a[href]")
            
            for link_elem in all_links:
                try:
                    href = await link_elem.get_attribute("href")
                    if not href:
                        continue
                    
                    absolute_url = urljoin(current_url, href)
                    
                    # Must be same domain
                    if not self._is_same_domain(absolute_url, domain):
                        continue
                    
                    # Clean URL
                    clean_url = self._clean_url(absolute_url)
                    
                    # Skip if already found
                    if clean_url in product_links:
                        continue
                    
                    # Check if it looks like a product URL
                    if self._looks_like_product_url(clean_url):
                        # Additional validation: check link context
                        parent = link_elem
                        for _ in range(3):  # Check up to 3 levels up
                            try:
                                parent = await parent.evaluate_handle("el => el.parentElement")
                                parent_class = await parent.get_attribute("class")
                                if parent_class and any(kw in parent_class.lower() for kw in ['product', 'item', 'card']):
                                    product_links.add(clean_url)
                                    break
                            except:
                                break
                    
                except Exception as e:
                    continue
        
        # Strategy 4: If still no links, check for images linked to pages
        if len(product_links) < 3:
            img_links = soup.find_all('a', href=True)
            for link in img_links:
                if link.find('img'):
                    href = link.get('href')
                    absolute_url = urljoin(current_url, href)
                    if self._is_same_domain(absolute_url, domain):
                        # If the link contains an image, it might be a product
                        clean_url = self._clean_url(absolute_url)
                        if len(urlparse(clean_url).path.split('/')) >= 2:  # Has some depth
                            product_links.add(clean_url)
        
        logger.info(f"📦 Found {len(product_links)} product links on page")
        
        # Log some examples for debugging
        if product_links:
            examples = list(product_links)[:3]
            logger.debug(f"Example product links: {examples}")
        
        return list(product_links)

    async def _find_pagination_multi_strategy(self, page: Page, soup: BeautifulSoup, 
                                               current_url: str, domain: str) -> List[str]:
        """Find pagination using multiple strategies"""
        next_pages = set()
        
        # Strategy 1: Use learned pagination selectors
        for selector in self.site_patterns.pagination_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    href = await element.get_attribute("href")
                    if href:
                        absolute_url = urljoin(current_url, href)
                        if self._is_same_domain(absolute_url, domain):
                            next_pages.add(self._clean_url(absolute_url))
            except:
                continue
        
        # Strategy 2: Standard pagination selectors
        pagination_selectors = [
            'a[rel="next"]', 'a[class*="next"]', 'link[rel="next"]',
            'a[class*="pagination"]', 'button[class*="next"]',
            '[class*="pagination"] a', '[class*="pager"] a',
            'a[aria-label*="next" i]', 'a[title*="next" i]',
        ]
        
        for selector in pagination_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    href = await element.get_attribute("href")
                    if href:
                        absolute_url = urljoin(current_url, href)
                        if self._is_same_domain(absolute_url, domain):
                            next_pages.add(self._clean_url(absolute_url))
            except:
                continue
        
        # Strategy 3: Query parameter pagination (page=N, p=N)
        parsed_url = urlparse(current_url)
        query_params = parse_qs(parsed_url.query)
        
        for param_name in ['page', 'p', 'pg', 'pagenum']:
            if param_name in query_params:
                try:
                    current_page = int(query_params[param_name][0])
                    # Add next few pages
                    for next_page_num in range(current_page + 1, min(current_page + 4, current_page + 10)):
                        new_params = query_params.copy()
                        new_params[param_name] = [str(next_page_num)]
                        new_query = urlencode(new_params, doseq=True)
                        new_url = urlunparse((
                            parsed_url.scheme, parsed_url.netloc, parsed_url.path,
                            parsed_url.params, new_query, ''
                        ))
                        next_pages.add(new_url)
                except:
                    pass
        
        # Strategy 4: Look for numbered pagination links
        numbered_page_links = soup.find_all('a', href=True, text=re.compile(r'^\d+$'))
        for link in numbered_page_links:
            href = link.get('href')
            absolute_url = urljoin(current_url, href)
            if self._is_same_domain(absolute_url, domain):
                next_pages.add(self._clean_url(absolute_url))
        
        logger.debug(f"Found {len(next_pages)} pagination links")
        return list(next_pages)

    async def _extract_promising_links(self, page: Page, soup: BeautifulSoup, 
                                       current_url: str, domain: str) -> List[Tuple[str, int]]:
        """Extract all promising links with priority scores"""
        links_with_priority = []
        
        link_elements = await page.query_selector_all("a[href]")
        
        for element in link_elements[:100]:  # Limit to avoid slowdown
            try:
                href = await element.get_attribute("href")
                if not href:
                    continue
                
                absolute_url = urljoin(current_url, href)
                
                if not self._is_same_domain(absolute_url, domain):
                    continue
                
                clean_url = self._clean_url(absolute_url)
                
                # Calculate priority
                priority = self._calculate_enhanced_link_priority(clean_url)
                
                if priority > 0:
                    links_with_priority.append((clean_url, priority))
                    
            except:
                continue
        
        # Sort by priority
        links_with_priority.sort(key=lambda x: -x[1])
        
        return links_with_priority

    def _calculate_enhanced_link_priority(self, url: str) -> int:
        """Enhanced priority calculation"""
        priority = 10
        url_lower = url.lower()
        
        # Very high priority (likely products)
        very_high = ['/product/', '/item/', '/p/', '/shop/', '/buy/']
        very_high.extend([p.lower() for p in self.site_patterns.product_url_patterns])
        if any(kw in url_lower for kw in very_high):
            priority += 60
        
        # High priority (category/collection)
        high = ['/collection/', '/category/', '/catalog/', '/jewelry', '/jewellery']
        if any(kw in url_lower for kw in high):
            priority += 40
        
        # Medium priority (specific product types)
        medium = ['/ring', '/necklace', '/earring', '/bracelet', '/pendant', '/chain']
        if any(kw in url_lower for kw in medium):
            priority += 30
        
        # Low priority but worth checking
        low = ['/new', '/best', '/featured', '/sale', '/trending']
        if any(kw in url_lower for kw in low):
            priority += 20
        
        # Penalties (likely not products)
        avoid = [
            '/blog', '/about', '/contact', '/cart', '/checkout', '/account', 
            '/login', '/register', '/search', '/help', '/faq', '/privacy', 
            '/terms', '/shipping', '/returns', '/reviews', '/warranty',
            '.pdf', '.jpg', '.png', '.gif', '.css', '.js', '/cdn-cgi/'
        ]
        if any(kw in url_lower for kw in avoid):
            priority = 0
        
        # URL depth bonus (deeper URLs more likely to be products)
        depth = len(urlparse(url).path.split('/')) - 1
        if 2 <= depth <= 4:
            priority += 5 * depth
        elif depth > 4:
            priority -= 5
        
        return priority

    def _should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped entirely"""
        url_lower = url.lower()
        
        skip_patterns = [
            '/cdn-cgi/', '/api/', '/ajax/', '/.well-known/',
            '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.css', '.js', '.ico',
            '/cart', '/checkout', '/account', '/login', '/register',
            '/password', '/logout', '/wishlist', '/blog','/news',
        ]
        
        return any(pattern in url_lower for pattern in skip_patterns)

    def _looks_like_product_url(self, url: str) -> bool:
        """Enhanced product URL detection"""
        url_lower = url.lower()
        
        # Check learned patterns first
        for pattern in self.site_patterns.product_url_patterns:
            if pattern.lower() in url_lower:
                return True
        
        # Positive indicators
        product_indicators = [
            '/product', '/item', '/p/', '/jewel', '/jewelry-', '/jewellery',
            '/ring', '/necklace', '/earring', '/bracelet', '/pendant',
            '/chain', '/charm', '/bangle', '/anklet'
        ]
        
        # Negative indicators (pages that look like products but aren't)
        non_product = [
            '/blog', '/about', '/contact', '/cart', '/checkout','/news',
            '/account', '/login', '/register', '/search', '/help', '/faq',
            '/privacy', '/terms', '/shipping', '/returns', '/category/',
            '/collection/', '/collections/', '/products/', '/shop/',
            '.pdf', '.jpg', '.png', '.css', '.js', '/reviews/'
        ]
        
        has_product_indicator = any(ind in url_lower for ind in product_indicators)
        
        # If has clear product indicator and no exclusions
        if has_product_indicator:
            return True
        
        return False
    
    def _looks_like_product_url_sitemap(self, url: str) -> bool:
            """Enhanced product URL detection"""
            url_lower = url.lower()
            
            # Check learned patterns first
            for pattern in self.site_patterns.product_url_patterns:
                if pattern.lower() in url_lower:
                    return True
            
            # Positive indicators
            product_indicators = [
                '/product'
            ]
            
            # Negative indicators (pages that look like products but aren't)
            non_product = [
                '/blog', '/about', '/contact', '/cart', '/checkout','/news',
                '/account', '/login', '/register', '/search', '/help', '/faq',
                '/privacy', '/terms', '/shipping', '/returns', '/category/',
                '/collection/', '/collections/', '/products/', '/shop/',
                '.pdf', '.jpg', '.png', '.css', '.js', '/reviews/'
            ]
            
            has_product_indicator = any(ind in url_lower for ind in product_indicators)
            
            # If has clear product indicator and no exclusions
            if has_product_indicator:
                return True
            
            return False

    def _learn_url_pattern(self, url: str) -> None:
        """Learn URL patterns from confirmed product pages"""
        path = urlparse(url).path
        
        # Extract meaningful patterns
        segments = [s for s in path.split('/') if s]
        
        if len(segments) >= 2:
            # Pattern like /products/item-name
            pattern = '/' + segments[0] + '/'
            if pattern not in self.site_patterns.product_url_patterns:
                self.site_patterns.product_url_patterns.append(pattern)
                logger.info(f"📚 Learned new URL pattern: {pattern}")

    def _validate_product_data(self, product_data: Dict) -> bool:
        """Validate that extracted data is actually from a product page"""
        # Must have URL
        if not product_data.get('url'):
            return False
        
        # Must have HTML content
        if not product_data.get('html') or len(product_data.get('html', '')) < 500:
            return False
        
        # Check for product indicators in HTML
        html_lower = product_data.get('html', '').lower()
        
        # Must have at least 2 of these indicators
        indicators_found = 0
        if 'price' in html_lower or '$' in html_lower or '€' in html_lower or '₹' in html_lower or 'rs' in html_lower :
            indicators_found += 1
        if 'add to cart' in html_lower or 'add to bag' in html_lower or 'buy now' in html_lower:
            indicators_found += 1
        if 'product' in html_lower:
            indicators_found += 1
        if len(product_data.get('images', [])) > 0:
            indicators_found += 1
        
        return indicators_found >= 1

    def _is_same_domain(self, url: str, domain: str) -> bool:
        """Check if URL is from same domain"""
        return urlparse(url).netloc == domain or urlparse(url).netloc == f"www.{domain}" or urlparse(url).netloc == domain.replace("www.", "")

    def _clean_url(self, url: str) -> str:
        """Remove fragments and normalize URL"""
        parsed = urlparse(url)
        # Remove fragment and trailing slash
        path = parsed.path.rstrip('/')
        query = parsed.query
        
        return f"{parsed.scheme}://{parsed.netloc}{path}" + (f"?{query}" if query else "")

    async def _scroll_page(self, page: Page) -> None:
        """Scroll page to trigger lazy loading"""
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
            logger.debug(f"Error scrolling page: {str(e)}")

    async def _extract_product_data(self, page: Page, content: str, url: str) -> Dict:
        """Extract raw product data from a product page"""
        soup = BeautifulSoup(content, 'lxml')
        
        # Extract images
        images = await self._extract_images_enhanced(page, soup)
        
        # Extract basic product info for validation
        title = await page.title()
        
        # Try to extract price for validation
        price_text = None
        price_elem = soup.find(attrs={"class": lambda x: x and "price" in str(x).lower()})
        if price_elem:
            price_text = price_elem.get_text(strip=True)
        
        product_data = {
            "url": url,
            "html": content,
            "images": images,
            "title": title,
            "price_text": price_text,
        }
        
        return product_data

    async def _extract_images_enhanced(self, page: Page, soup: BeautifulSoup) -> List[str]:
        """Enhanced image extraction"""
        images = set()
        
        # Comprehensive image selectors
        img_selectors = [
            "img[class*='product']", "img[class*='gallery']", "img[class*='main']",
            "img[class*='primary']", "img[itemprop='image']", "img[class*='zoom']",
            ".product-image img", ".product-gallery img", ".product-photos img",
            "[data-zoom-image]", "picture source", "[class*='image'] img",
            "main img", "article img", "[role='main'] img",
        ]
        
        for selector in img_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    # Try multiple attributes
                    for attr in ['src', 'data-src', 'data-lazy-src', 'srcset', 'data-zoom-image', 'data-image']:
                        src = await element.get_attribute(attr)
                        if src and not src.startswith("data:") and len(src) > 10:
                            # Handle srcset
                            if attr == 'srcset':
                                # Get largest image from srcset
                                srcset_parts = src.split(',')
                                if srcset_parts:
                                    src = srcset_parts[-1].strip().split()[0]
                            
                            absolute_url = urljoin(page.url, src)
                            
                            # Filter out tiny images (icons, logos)
                            if not any(x in absolute_url.lower() for x in ['icon', 'logo', 'sprite', 'pixel']):
                                images.add(absolute_url)
                
                if len(images) >= self.settings.max_images_per_product:
                    break
                    
            except Exception as e:
                logger.debug(f"Error extracting images with selector {selector}: {str(e)}")
                continue
        
        # If no images found, get all images on page
        if len(images) == 0:
            all_imgs = soup.find_all('img', src=True)
            for img in all_imgs[:10]:
                src = img.get('src')
                if src and not src.startswith('data:'):
                    absolute_url = urljoin(page.url, src)
                    images.add(absolute_url)
        
        return list(images)[:self.settings.max_images_per_product]