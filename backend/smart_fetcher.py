"""
Smart Fetcher - Multi-strategy approach to bypass anti-bot
Tries different methods until one works
"""

import asyncio
import logging
import time
import re
from typing import Optional, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from flaresolverr_client import FlareSolverrClient

logger = logging.getLogger(__name__)

# Try stealth import
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


class SmartFetcher:
    """
    Smart fetcher that tries multiple strategies:
    1. Direct Googlebot request (fastest, works for non-protected sites)
    2. Stealth Chrome with Googlebot UA (for light Cloudflare)
    3. FlareSolverr (for heavy Cloudflare protection)
    """

    # User Agents
    GOOGLEBOT_UA = (
        "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.184 Mobile Safari/537.36 "
        "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    )

    CHROME_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )

    CLOUDFLARE_INDICATORS = [
        "just a moment",
        "checking your browser",
        "please wait",
        "ddos protection",
        "ray id",
        "cf-browser-verification",
        "challenge-running",
        "_cf_chl",
        "cdn-cgi/challenge",
    ]

    def __init__(self, timeout: int = 30000, max_cf_wait: int = 20, proxy_url: str = None):
        self.timeout = timeout
        self.max_cf_wait = max_cf_wait
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.flaresolverr: Optional[FlareSolverrClient] = None
        self.flaresolverr_available: bool = False
        # Czech proxy fallback (format: http://user:pass@host:port)
        import os
        self.proxy_url = proxy_url or os.getenv("PROXY_URL")

    async def start(self):
        """Initialize browser and FlareSolverr"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--window-size=1920,1080',
            ]
        )

        # Initialize FlareSolverr client
        self.flaresolverr = FlareSolverrClient()
        await self.flaresolverr.start()
        self.flaresolverr_available = await self.flaresolverr.is_available()
        if self.flaresolverr_available:
            logger.info("FlareSolverr is available - will use for Cloudflare bypass")
        else:
            logger.warning("FlareSolverr not available - some sites may not work")

    async def stop(self):
        """Cleanup"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self.flaresolverr:
            await self.flaresolverr.stop()

    def _is_cloudflare(self, html: str) -> bool:
        """Check if Cloudflare challenge"""
        html_lower = html.lower()
        return any(ind in html_lower for ind in self.CLOUDFLARE_INDICATORS)

    def _extract_seo_data(self, html: str) -> dict:
        """Extract SEO data from HTML"""
        data = {}

        # Title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
        if title_match:
            data['title'] = title_match.group(1).strip()

        # H1
        h1_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
        if h1_match:
            data['h1'] = h1_match.group(1).strip()

        # Meta description
        desc_match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
            html, re.I
        )
        if not desc_match:
            desc_match = re.search(
                r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']description["\']',
                html, re.I
            )
        if desc_match:
            data['description'] = desc_match.group(1).strip()

        # Canonical
        canonical_match = re.search(
            r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
            html, re.I
        )
        if canonical_match:
            data['canonical'] = canonical_match.group(1).strip()

        return data

    async def _fetch_with_ua(self, url: str, user_agent: str, use_stealth: bool = False) -> dict:
        """Fetch URL with specific UA"""
        context = None
        page = None
        start_time = time.time()

        try:
            context = await self.browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
            )

            page = await context.new_page()

            # Apply stealth if requested and available
            if use_stealth and HAS_STEALTH:
                await stealth_async(page)

            # Navigate
            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)

            if not response:
                return {"success": False, "error": "No response"}

            html = await page.content()

            # Check Cloudflare
            if self._is_cloudflare(html):
                # Wait for challenge to resolve
                for _ in range(self.max_cf_wait):
                    await asyncio.sleep(1)
                    html = await page.content()
                    if not self._is_cloudflare(html):
                        break

                # Final check
                if self._is_cloudflare(html):
                    return {
                        "success": False,
                        "error": "Cloudflare challenge not resolved",
                        "cloudflare": True
                    }

            # Wait for dynamic content
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
                html = await page.content()
            except:
                pass

            return {
                "success": True,
                "html": html,
                "status_code": response.status,
                "final_url": page.url,
                "fetch_time_ms": int((time.time() - start_time) * 1000),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "fetch_time_ms": int((time.time() - start_time) * 1000),
            }

        finally:
            if page:
                await page.close()
            if context:
                await context.close()

    async def _fetch_with_proxy(self, url: str) -> dict:
        """Fetch URL through Czech proxy with Googlebot UA"""
        if not self.proxy_url:
            return {"success": False, "error": "No proxy configured"}

        context = None
        page = None
        start_time = time.time()

        try:
            context = await self.browser.new_context(
                user_agent=self.GOOGLEBOT_UA,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="Europe/Prague",
                proxy={"server": self.proxy_url}
            )

            page = await context.new_page()

            if HAS_STEALTH:
                await stealth_async(page)

            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)

            if not response:
                return {"success": False, "error": "No response via proxy"}

            html = await page.content()

            # Wait for Cloudflare if detected
            if self._is_cloudflare(html):
                for _ in range(self.max_cf_wait):
                    await asyncio.sleep(1)
                    html = await page.content()
                    if not self._is_cloudflare(html):
                        break

            # Wait for dynamic content
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
                html = await page.content()
            except:
                pass

            return {
                "success": True,
                "html": html,
                "status_code": response.status,
                "final_url": page.url,
                "fetch_time_ms": int((time.time() - start_time) * 1000),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "fetch_time_ms": int((time.time() - start_time) * 1000),
            }

        finally:
            if page:
                await page.close()
            if context:
                await context.close()

    async def fetch(self, url: str) -> dict:
        """
        Smart fetch - tries multiple strategies in order:
        1. Googlebot UA direct (fastest, works for non-protected sites)
        2. Googlebot UA with stealth (for light Cloudflare)
        3. FlareSolverr with Googlebot UA (for heavy Cloudflare)
        4. Czech proxy fallback (last resort)
        """
        if not self.browser:
            return {"success": False, "error": "Browser not initialized"}

        start_time = time.time()

        # Strategy 1: Direct Googlebot UA (fastest)
        logger.info(f"[Strategy 1] Trying direct Googlebot UA for {url}")
        result = await self._fetch_with_ua(url, self.GOOGLEBOT_UA, use_stealth=False)

        if result.get("success") and not self._is_cloudflare(result.get("html", "")):
            result["strategy"] = "googlebot_direct"
            result["seo_data"] = self._extract_seo_data(result.get("html", ""))
            return result

        # Strategy 2: Googlebot UA with stealth (for light Cloudflare)
        logger.info(f"[Strategy 2] Trying Googlebot UA with stealth for {url}")
        result = await self._fetch_with_ua(url, self.GOOGLEBOT_UA, use_stealth=True)

        if result.get("success") and not self._is_cloudflare(result.get("html", "")):
            result["strategy"] = "googlebot_stealth"
            result["seo_data"] = self._extract_seo_data(result.get("html", ""))
            return result

        # Strategy 3: FlareSolverr (for heavy Cloudflare)
        if self.flaresolverr_available:
            logger.info(f"[Strategy 3] Trying FlareSolverr for {url}")
            result = await self.flaresolverr.fetch(url, googlebot_ua=True)

            if result.get("success") and not self._is_cloudflare(result.get("html", "")):
                result["strategy"] = "flaresolverr"
                result["seo_data"] = self._extract_seo_data(result.get("html", ""))
                return result

        # Strategy 4: Czech proxy fallback
        if self.proxy_url:
            logger.info(f"[Strategy 4] Trying Czech proxy for {url}")
            result = await self._fetch_with_proxy(url)

            if result.get("success") and not self._is_cloudflare(result.get("html", "")):
                result["strategy"] = "czech_proxy"
                result["seo_data"] = self._extract_seo_data(result.get("html", ""))
                return result

        # All strategies failed
        result["fetch_time_ms"] = int((time.time() - start_time) * 1000)
        result["error"] = "All bypass strategies failed - Cloudflare protection too strong"
        return result


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test():
        fetcher = SmartFetcher()
        await fetcher.start()

        test_urls = [
            "https://example.com",
            "https://chickenroad.io",
            "https://reseaurural.fr",
        ]

        for url in test_urls:
            print(f"\n{'='*60}")
            print(f"Testing: {url}")
            result = await fetcher.fetch(url)
            print(f"Success: {result.get('success')}")
            print(f"Strategy: {result.get('strategy', 'N/A')}")
            print(f"Time: {result.get('fetch_time_ms')}ms")

            if result.get('success'):
                seo = result.get('seo_data', {})
                print(f"Title: {seo.get('title', 'N/A')}")
                print(f"H1: {seo.get('h1', 'N/A')}")
                if result.get('warning'):
                    print(f"Warning: {result['warning']}")
            else:
                print(f"Error: {result.get('error')}")

        await fetcher.stop()

    asyncio.run(test())
