"""
Googlebot Fetcher
Fetches pages using Playwright with Googlebot User-Agent
"""

import asyncio
import time
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext


class GooglebotFetcher:
    """
    Fetches pages as Googlebot using Playwright.
    Uses mobile Googlebot User-Agent for best compatibility.
    """

    # Mobile Googlebot User-Agent (most common)
    GOOGLEBOT_UA = (
        "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36 "
        "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    )

    # Desktop Googlebot User-Agent (fallback)
    GOOGLEBOT_DESKTOP_UA = (
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    )

    def __init__(self, headless: bool = True, timeout: int = 15000):
        self.headless = headless
        self.timeout = timeout
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def start(self):
        """Initialize browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless
        )
        self.context = await self.browser.new_context(
            user_agent=self.GOOGLEBOT_UA,
            viewport={"width": 412, "height": 732},  # Mobile viewport
            device_scale_factor=2.625,
            is_mobile=True,
            has_touch=True
        )

    async def stop(self):
        """Cleanup browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def fetch(self, url: str) -> dict:
        """
        Fetch a URL as Googlebot.

        Returns:
            dict with keys:
                - success: bool
                - html: str (rendered HTML)
                - status_code: int
                - fetch_time_ms: int
                - error: str (if failed)
        """
        if not self.context:
            return {
                "success": False,
                "error": "Fetcher not initialized",
                "fetch_time_ms": 0
            }

        start_time = time.time()
        page = None

        try:
            page = await self.context.new_page()

            # Navigate to URL - use domcontentloaded for faster results
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout
            )

            # Brief wait for JS execution
            await page.wait_for_timeout(500)

            # Get rendered HTML
            html = await page.content()

            fetch_time_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "html": html,
                "status_code": response.status if response else 200,
                "fetch_time_ms": fetch_time_ms
            }

        except Exception as e:
            fetch_time_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": str(e),
                "fetch_time_ms": fetch_time_ms
            }

        finally:
            if page:
                await page.close()


# Test
if __name__ == "__main__":
    async def test():
        fetcher = GooglebotFetcher()
        await fetcher.start()

        result = await fetcher.fetch("https://example.com")
        print(f"Success: {result['success']}")
        print(f"Time: {result['fetch_time_ms']}ms")
        if result['success']:
            print(f"HTML length: {len(result['html'])}")

        await fetcher.stop()

    asyncio.run(test())
