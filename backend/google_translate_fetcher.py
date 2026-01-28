"""
Google Translate Proxy Fetcher - THE LOOPHOLE!

affiliate.fm использует Google Translate как прокси:
https://translate.google.com/translate?sl=auto&tl=en&u=TARGET_URL

Google Translate проксирует весь контент через доверенные IP Google.
Сайты не блокируют Google Translate, потому что это легитимный сервис Google.

Два метода:
1. HTTP запрос к translate.google.com (быстро, работает для Wikipedia)
2. Playwright с Google Translate page (для сложных сайтов как ProductHunt)
"""

import aiohttp
import asyncio
import re
import time
import logging
from typing import Optional
from urllib.parse import quote, urlencode

# Try Playwright import
try:
    from playwright.async_api import async_playwright, Browser
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

logger = logging.getLogger(__name__)


class GoogleTranslateFetcher:
    """
    Fetches URLs through Google Translate proxy.
    This bypasses most anti-bot protections because requests come from Google's IP.

    Methods:
    1. HTTP request (fast, works for Wikipedia and simple sites)
    2. Playwright browser (for complex JS-heavy sites like ProductHunt)
    """

    # Google Translate proxy URL format
    TRANSLATE_URL = "https://translate.google.com/translate"

    # Alternative: website mode (used by affiliate.fm)
    WEBSITE_URL = "https://translate.google.com/website"

    def __init__(self, timeout: int = 30, use_playwright: bool = True):
        self.timeout = timeout
        self.use_playwright = use_playwright and HAS_PLAYWRIGHT
        self.session: Optional[aiohttp.ClientSession] = None
        self.playwright = None
        self.browser: Optional[Browser] = None

    async def start(self):
        """Initialize aiohttp session and optionally Playwright browser"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

        # Initialize Playwright for complex sites
        if self.use_playwright:
            try:
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                    ]
                )
                logger.info("Playwright browser initialized for Google Translate")
            except Exception as e:
                logger.warning(f"Failed to initialize Playwright: {e}")
                self.use_playwright = False

    async def stop(self):
        """Cleanup"""
        if self.session:
            await self.session.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def _build_translate_url(self, target_url: str, method: str = "translate") -> str:
        """
        Build Google Translate proxy URL

        Methods:
        - "translate": Standard translation page
        - "website": Website translation mode (like affiliate.fm uses)
        """
        if method == "website":
            # Format: https://translate.google.com/website?sl=auto&tl=en&u=URL
            params = {
                "sl": "auto",  # Source language: auto-detect
                "tl": "en",    # Target language: English
                "hl": "en",    # Interface language
                "u": target_url
            }
            return f"{self.WEBSITE_URL}?{urlencode(params)}"
        else:
            # Format: https://translate.google.com/translate?sl=auto&tl=en&u=URL
            params = {
                "sl": "auto",
                "tl": "en",
                "u": target_url
            }
            return f"{self.TRANSLATE_URL}?{urlencode(params)}"

    def _clean_translated_html(self, html: str, original_url: str) -> str:
        """
        Clean up Google Translate wrapper from HTML.
        Remove translation UI elements and restore original content.
        """
        # Remove Google Translate toolbar/frame
        html = re.sub(r'<div[^>]*id="gt-nvframe"[^>]*>.*?</div>', '', html, flags=re.DOTALL)
        html = re.sub(r'<div[^>]*class="[^"]*goog-te-[^"]*"[^>]*>.*?</div>', '', html, flags=re.DOTALL)

        # Remove Google Translate scripts
        html = re.sub(r'<script[^>]*translate\.google[^>]*>.*?</script>', '', html, flags=re.DOTALL)

        # Fix translated URLs back to original domain
        # Google Translate rewrites URLs like: translate.googleusercontent.com/translate_c?...&u=original_url
        html = re.sub(
            r'https?://translate\.googleusercontent\.com/translate_c\?[^"\']*u=([^"\'&]+)',
            lambda m: m.group(1),
            html
        )

        return html

    async def fetch(self, url: str) -> dict:
        """
        Fetch URL through Google Translate proxy.

        Tries in order:
        1. HTTP request (fast)
        2. Playwright browser (for JS-heavy sites)

        Returns:
            dict with success, html, status_code, fetch_time_ms, etc.
        """
        if not self.session:
            await self.start()

        start_time = time.time()

        # Method 1: Try HTTP request first (fast)
        for method in ["website", "translate"]:
            try:
                proxy_url = self._build_translate_url(url, method)
                logger.info(f"[GoogleTranslate] Trying {method} method for {url}")

                async with self.session.get(proxy_url) as response:
                    if response.status == 200:
                        html = await response.text()

                        # Check if we got actual content (not error page)
                        if len(html) > 1000 and "<html" in html.lower():
                            # Clean up Google Translate wrapper
                            cleaned_html = self._clean_translated_html(html, url)

                            return {
                                "success": True,
                                "html": cleaned_html,
                                "raw_html": html,  # Keep original for debugging
                                "status_code": 200,
                                "final_url": url,
                                "fetch_time_ms": int((time.time() - start_time) * 1000),
                                "method": f"google_translate_{method}",
                                "proxy_url": proxy_url
                            }

                    logger.warning(f"[GoogleTranslate] {method} returned status {response.status}")

            except asyncio.TimeoutError:
                logger.warning(f"[GoogleTranslate] {method} timeout for {url}")
            except Exception as e:
                logger.warning(f"[GoogleTranslate] {method} error: {e}")

        # Method 2: Try Playwright as fallback (for JS-heavy sites like ProductHunt)
        if self.use_playwright and self.browser:
            logger.info(f"[GoogleTranslate] HTTP failed, trying Playwright for {url}")
            result = await self._fetch_with_playwright(url)
            if result.get("success"):
                return result

        # All methods failed
        return {
            "success": False,
            "error": "Google Translate proxy failed (HTTP + Playwright)",
            "fetch_time_ms": int((time.time() - start_time) * 1000),
        }

    async def fetch_raw(self, url: str) -> dict:
        """
        Fetch URL and return raw HTML without cleaning.
        Useful for debugging or when you need the Google Translate frame.
        """
        if not self.session:
            await self.start()

        start_time = time.time()
        proxy_url = self._build_translate_url(url, "website")

        try:
            async with self.session.get(proxy_url) as response:
                html = await response.text()
                return {
                    "success": response.status == 200,
                    "html": html,
                    "status_code": response.status,
                    "fetch_time_ms": int((time.time() - start_time) * 1000),
                    "proxy_url": proxy_url
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "fetch_time_ms": int((time.time() - start_time) * 1000),
            }

    async def _fetch_with_playwright(self, url: str) -> dict:
        """
        Fetch URL through Google Translate using Playwright browser.
        This works for complex JS-heavy sites like ProductHunt.

        The browser loads the Google Translate page which then loads
        the target site through Google's proxy infrastructure.
        """
        if not self.browser:
            return {"success": False, "error": "Playwright not available"}

        start_time = time.time()
        context = None
        page = None

        try:
            context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            page = await context.new_page()

            # Navigate to Google Translate page with target URL
            proxy_url = self._build_translate_url(url, "translate")
            logger.info(f"[GoogleTranslate Playwright] Loading {proxy_url}")

            await page.goto(proxy_url, wait_until="domcontentloaded", timeout=self.timeout * 1000)

            # Wait for the translated content to load (iframe)
            # Google Translate loads content in an iframe
            await asyncio.sleep(3)  # Let JS execute

            # Try to get content from the main frame
            html = await page.content()

            # If there's an iframe with translated content, try to get it
            frames = page.frames
            for frame in frames:
                try:
                    if frame != page.main_frame:
                        frame_html = await frame.content()
                        if len(frame_html) > len(html):
                            html = frame_html
                except:
                    pass

            # Wait for more content if needed
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
                html = await page.content()
            except:
                pass

            # Clean up the HTML
            cleaned_html = self._clean_translated_html(html, url)

            return {
                "success": True,
                "html": cleaned_html,
                "raw_html": html,
                "status_code": 200,
                "final_url": url,
                "fetch_time_ms": int((time.time() - start_time) * 1000),
                "method": "google_translate_playwright",
                "proxy_url": proxy_url
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Playwright timeout",
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


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test():
        fetcher = GoogleTranslateFetcher()
        await fetcher.start()

        test_urls = [
            "https://wikipedia.org",
            "https://www.producthunt.com",
            "https://www.bbc.com",
        ]

        for url in test_urls:
            print(f"\n{'='*60}")
            print(f"Testing: {url}")
            result = await fetcher.fetch(url)
            print(f"Success: {result.get('success')}")
            print(f"Method: {result.get('method', 'N/A')}")
            print(f"Time: {result.get('fetch_time_ms')}ms")

            if result.get('success'):
                html = result.get('html', '')
                print(f"HTML length: {len(html)}")
                # Extract title
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
                if title_match:
                    print(f"Title: {title_match.group(1)[:50]}...")
            else:
                print(f"Error: {result.get('error')}")

        await fetcher.stop()

    asyncio.run(test())
