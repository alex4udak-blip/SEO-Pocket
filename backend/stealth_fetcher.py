"""
Stealth Googlebot Fetcher
Uses playwright-stealth to bypass Cloudflare and other anti-bot systems
"""

import asyncio
import logging
import time
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

# Try to import stealth
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False
    logger.warning("playwright-stealth not installed, running without stealth mode")


class StealthGooglebotFetcher:
    """
    Fetches pages as Googlebot with stealth capabilities to bypass anti-bot.

    Key features:
    - Googlebot User-Agent
    - Stealth mode to avoid detection
    - Waits for Cloudflare challenges to complete
    - Handles JavaScript rendering
    """

    # Googlebot Mobile User-Agent (most sites serve mobile-first)
    GOOGLEBOT_UA = (
        "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.184 Mobile Safari/537.36 "
        "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    )

    # Cloudflare challenge indicators
    CLOUDFLARE_INDICATORS = [
        "just a moment",
        "checking your browser",
        "please wait",
        "ddos protection",
        "cloudflare",
        "ray id",
        "cf-browser-verification",
        "challenge-running",
    ]

    def __init__(self, timeout: int = 30000, max_cf_wait: int = 15):
        self.timeout = timeout
        self.max_cf_wait = max_cf_wait  # Max seconds to wait for Cloudflare
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def start(self):
        """Initialize browser with stealth settings"""
        self.playwright = await async_playwright().start()

        # Launch with specific args to avoid detection
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
            ]
        )

        # Create context with Googlebot UA
        self.context = await self.browser.new_context(
            user_agent=self.GOOGLEBOT_UA,
            viewport={"width": 412, "height": 915},  # Mobile viewport
            locale="en-US",
            timezone_id="America/New_York",
            java_script_enabled=True,
            ignore_https_errors=True,
        )

        # Set extra headers that Googlebot might send
        await self.context.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        })

    async def stop(self):
        """Cleanup browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def _is_cloudflare_challenge(self, html: str) -> bool:
        """Check if page shows Cloudflare challenge"""
        html_lower = html.lower()
        return any(ind in html_lower for ind in self.CLOUDFLARE_INDICATORS)

    async def _wait_for_cloudflare(self, page: Page) -> bool:
        """
        Wait for Cloudflare challenge to complete.
        Returns True if challenge was detected and resolved.
        """
        start = time.time()

        while time.time() - start < self.max_cf_wait:
            html = await page.content()

            if not self._is_cloudflare_challenge(html):
                return True

            # Wait a bit and check again
            await asyncio.sleep(1)

            # Also wait for network to be idle
            try:
                await page.wait_for_load_state("networkidle", timeout=2000)
            except:
                pass

        return False

    async def fetch(self, url: str) -> dict:
        """
        Fetch URL as Googlebot with stealth mode.

        Returns:
            dict with success, html, status_code, error, fetch_time_ms
        """
        if not self.context:
            return {"success": False, "error": "Browser not initialized"}

        start_time = time.time()
        page = None

        try:
            page = await self.context.new_page()

            # Apply stealth if available
            if HAS_STEALTH:
                await stealth_async(page)

            # Navigate
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout
            )

            if not response:
                return {
                    "success": False,
                    "error": "No response from server",
                    "fetch_time_ms": int((time.time() - start_time) * 1000)
                }

            # Check for Cloudflare and wait if needed
            html = await page.content()
            if self._is_cloudflare_challenge(html):
                logger.info(f"Cloudflare challenge detected for {url}, waiting...")
                resolved = await self._wait_for_cloudflare(page)
                if resolved:
                    html = await page.content()
                else:
                    logger.warning(f"Cloudflare challenge not resolved for {url}")

            # Wait for any dynamic content
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
                html = await page.content()
            except:
                pass

            return {
                "success": True,
                "html": html,
                "status_code": response.status,
                "fetch_time_ms": int((time.time() - start_time) * 1000),
                "url": page.url,  # Final URL after redirects
            }

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return {
                "success": False,
                "error": str(e),
                "fetch_time_ms": int((time.time() - start_time) * 1000)
            }

        finally:
            if page:
                await page.close()


# Test
if __name__ == "__main__":
    async def test():
        fetcher = StealthGooglebotFetcher()
        await fetcher.start()

        # Test with cloaked site
        test_urls = [
            "https://chickenroad.io",
            "https://reseaurural.fr",
            "https://casino-ohne.gaststaette-hillenbrand.de/",
        ]

        for url in test_urls:
            print(f"\n{'='*60}")
            print(f"Testing: {url}")
            result = await fetcher.fetch(url)
            print(f"Success: {result.get('success')}")
            print(f"Time: {result.get('fetch_time_ms')}ms")
            if result.get('success'):
                html = result.get('html', '')
                # Extract title
                import re
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
                if title_match:
                    print(f"Title: {title_match.group(1)}")
                print(f"HTML length: {len(html)}")
            else:
                print(f"Error: {result.get('error')}")

        await fetcher.stop()

    asyncio.run(test())
