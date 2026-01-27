"""
Google Cache Fetcher
Fetches cached version of pages from Google's index using Playwright

Supports proxy via GOOGLE_CACHE_PROXY env variable:
  - Format: http://user:pass@host:port or http://host:port
  - Required for production to avoid IP blocking
"""

import asyncio
import os
import re
import time
import logging
from typing import Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext

logger = logging.getLogger(__name__)


class GoogleCacheFetcher:
    """
    Fetches page data from Google's cache using Playwright.
    This provides what Google has indexed, not current page state.

    Note: Google aggressively blocks cache requests. Without a proxy,
    you may get blocked after a few requests. Set GOOGLE_CACHE_PROXY
    env variable to use a rotating proxy service.
    """

    # Regular browser user agent (not Googlebot)
    BROWSER_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Block detection patterns
    BLOCK_PATTERNS = [
        "unusual traffic",
        "ungewöhnlichen datenverkehr",  # German
        "tráfico inusual",  # Spanish
        "трафик необычный",  # Russian
        "captcha",
        "sorry/index",
    ]

    def __init__(self, timeout: int = 15000, proxy: Optional[str] = None):
        self.timeout = timeout
        self.proxy = proxy or os.getenv("GOOGLE_CACHE_PROXY")
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._blocked = False  # Track if we're blocked by Google
        self._blocked_time = 0  # When we got blocked
        self._block_cooldown = 300  # 5 minutes cooldown after block
        self._cache: dict = {}  # Simple in-memory cache
        self._cache_ttl = 3600  # 1 hour cache

    async def start(self):
        """Initialize browser for Google Cache requests"""
        self.playwright = await async_playwright().start()

        # Configure proxy if available
        browser_args = {"headless": True}
        if self.proxy:
            logger.info(f"Using proxy for Google Cache: {self.proxy.split('@')[-1] if '@' in self.proxy else self.proxy}")
            browser_args["proxy"] = {"server": self.proxy}

        self.browser = await self.playwright.chromium.launch(**browser_args)
        self.context = await self.browser.new_context(
            user_agent=self.BROWSER_UA,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York"
        )

    async def stop(self):
        """Cleanup browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def _is_blocked(self, html: str) -> bool:
        """Check if response indicates we're blocked by Google"""
        html_lower = html.lower()
        return any(pattern in html_lower for pattern in self.BLOCK_PATTERNS)

    def _get_from_cache(self, url: str) -> Optional[dict]:
        """Get cached result if still valid"""
        if url in self._cache:
            cached_time, cached_result = self._cache[url]
            if time.time() - cached_time < self._cache_ttl:
                logger.info(f"Cache hit for {url}")
                return cached_result
            else:
                del self._cache[url]
        return None

    def _save_to_cache(self, url: str, result: dict):
        """Save result to cache"""
        self._cache[url] = (time.time(), result)

    async def get_google_cache_data(self, url: str) -> dict:
        """
        Get cached data from Google for a URL.

        Returns:
        - cache_html: Full HTML from Google Cache
        - indexed_title: Title from cached page
        - indexed_description: Meta description from cached page
        - google_canonical: Canonical URL from cached page
        - cache_date: When Google cached the page
        - hreflang: Hreflang tags from cached page
        """
        # Check in-memory cache first
        cached = self._get_from_cache(url)
        if cached:
            return cached

        # If we're blocked, check if cooldown expired
        if self._blocked:
            if time.time() - self._blocked_time > self._block_cooldown:
                logger.info("Block cooldown expired, retrying Google Cache")
                self._blocked = False
            else:
                logger.warning("Skipping Google Cache - currently blocked")
                return {"success": False, "error": "Rate limited by Google", "blocked": True}

        if not self.context:
            return {"success": False, "error": "Browser not initialized"}

        start_time = time.time()
        result = {
            "success": False,
            "cache_html": None,
            "google_canonical": None,
            "cache_date": None,
            "indexed_title": None,
            "indexed_description": None,
            "indexed_h1": None,
            "indexed_hreflang": [],
            "indexed_html_lang": None,
            "site_indexed": False
        }

        page = None
        try:
            page = await self.context.new_page()

            # Fetch from Google Cache
            cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"

            response = await page.goto(
                cache_url,
                wait_until="domcontentloaded",  # Faster than networkidle
                timeout=self.timeout
            )

            if response and response.status == 200:
                html = await page.content()

                # Check if we're blocked
                if self._is_blocked(html):
                    logger.warning("Blocked by Google - rate limited")
                    self._blocked = True
                    self._blocked_time = time.time()
                    result["error"] = "Rate limited by Google"
                    result["blocked"] = True
                # Check if we got actual content (not Google error page)
                elif len(html) > 3000:
                    result["cache_html"] = html
                    result["site_indexed"] = True
                    result["success"] = True

                    # Parse the cached HTML
                    self._parse_cached_html(html, result)

                    # Cache successful results
                    self._save_to_cache(url, result)

            result["fetch_time_ms"] = int((time.time() - start_time) * 1000)

        except Exception as e:
            result["error"] = str(e)
            result["fetch_time_ms"] = int((time.time() - start_time) * 1000)

        finally:
            if page:
                await page.close()

        return result

    def _parse_cached_html(self, html: str, result: dict):
        """Parse cached HTML to extract SEO data"""
        soup = BeautifulSoup(html, "lxml")

        # Extract title
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Remove "affiliate.fm" suffix if present (from their wrapper)
            if title_text and title_text != "affiliate.fm":
                result["indexed_title"] = title_text

        # Extract meta description
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag and desc_tag.get("content"):
            result["indexed_description"] = desc_tag["content"]

        # Extract canonical
        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        if canonical_tag and canonical_tag.get("href"):
            result["google_canonical"] = canonical_tag["href"]

        # Extract H1
        h1_tag = soup.find("h1")
        if h1_tag:
            result["indexed_h1"] = h1_tag.get_text(strip=True)

        # Extract HTML lang
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            result["indexed_html_lang"] = html_tag["lang"]

        # Extract hreflang tags
        hreflang_tags = soup.find_all("link", attrs={"rel": "alternate", "hreflang": True})
        for tag in hreflang_tags:
            if tag.get("hreflang") and tag.get("href"):
                result["indexed_hreflang"].append({
                    "lang": tag["hreflang"],
                    "href": tag["href"]
                })

        # Also check for alternate without hreflang (just alternate URLs)
        if not result["indexed_hreflang"]:
            alternate_tags = soup.find_all("link", attrs={"rel": "alternate"})
            for tag in alternate_tags:
                if tag.get("href") and not tag.get("type"):  # Exclude RSS/Atom
                    result["indexed_hreflang"].append({
                        "lang": "alternate",
                        "href": tag["href"]
                    })

        # Try to extract cache date from Google's header
        # Google adds a div with cache info at the top
        cache_info = soup.find(string=re.compile(r'\d{1,2}\s+\w+\s+\d{4}'))
        if cache_info:
            date_match = re.search(
                r'(\d{1,2}\s+\w+\s+\d{4}\s+\d{2}:\d{2}:\d{2}\s+GMT)',
                str(cache_info)
            )
            if date_match:
                result["cache_date"] = date_match.group(1)


# Test
if __name__ == "__main__":
    async def test():
        fetcher = GoogleCacheFetcher()
        await fetcher.start()

        # Test with cloaking site
        result = await fetcher.get_google_cache_data(
            "https://casino-ohne.gaststaette-hillenbrand.de/"
        )
        print(f"Success: {result.get('success')}")
        print(f"Indexed: {result.get('site_indexed')}")
        print(f"Title: {result.get('indexed_title')}")
        print(f"H1: {result.get('indexed_h1')}")
        print(f"Canonical: {result.get('google_canonical')}")
        print(f"Lang: {result.get('indexed_html_lang')}")
        print(f"Hreflang: {result.get('indexed_hreflang')}")
        print(f"Time: {result.get('fetch_time_ms')}ms")

        if result.get('cache_html'):
            print(f"HTML length: {len(result['cache_html'])}")

        await fetcher.stop()

    asyncio.run(test())
