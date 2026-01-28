"""
Smart Fetcher Service.
Multi-strategy approach to fetch pages as Googlebot sees them.

Strategies (in order):
0. Google Translate proxy (THE LOOPHOLE! - works on most blocked sites)
1. Zyte API (for Cloudflare-protected sites - like affiliate.fm uses!)
2. Direct Googlebot UA (fastest, works for non-protected sites)
3. Stealth Googlebot UA (for light Cloudflare)
4. FlareSolverr (for heavy Cloudflare protection)
5. Proxy fallback (last resort)
"""

import asyncio
import random
import re
import time
from typing import Optional
from urllib.parse import quote, urlencode

import aiohttp
import httpx
from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__)

# Try Playwright import
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("Playwright not installed - browser strategies disabled")

# Try stealth import
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


class SmartFetcher:
    """
    Smart fetcher that tries multiple strategies to fetch pages as Googlebot.

    Strategies:
    0. Google Translate proxy (THE LOOPHOLE!)
    1. Zyte API (for Cloudflare bypass - same as affiliate.fm)
    2. Direct Googlebot UA
    3. Stealth Googlebot UA
    4. FlareSolverr
    5. Proxy fallback
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

    # Cloudflare indicators
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

    # Google Translate URLs
    TRANSLATE_URL = "https://translate.google.com/translate"
    WEBSITE_URL = "https://translate.google.com/website"

    def __init__(
        self,
        timeout: int = None,
        max_cf_wait: int = None,
        proxy_url: str = None,
        flaresolverr_url: str = None,
    ):
        """
        Initialize SmartFetcher.

        Args:
            timeout: Request timeout in ms
            max_cf_wait: Max seconds to wait for Cloudflare challenge
            proxy_url: Proxy URL for fallback strategy
            flaresolverr_url: FlareSolverr API URL
        """
        self.timeout = timeout or settings.fetch_timeout
        self.max_cf_wait = max_cf_wait or settings.max_cloudflare_wait
        self.proxy_url = proxy_url or settings.proxy_url
        self.flaresolverr_url = flaresolverr_url or settings.flaresolverr_url

        # Components
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.aiohttp_session: Optional[aiohttp.ClientSession] = None
        self.flaresolverr_client: Optional[httpx.AsyncClient] = None
        self.flaresolverr_available: bool = False

        # Zyte client
        self.zyte_client = None
        self.zyte_available: bool = False

    async def start(self) -> None:
        """Initialize browser and HTTP clients."""
        # Initialize aiohttp session for Google Translate
        self.aiohttp_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout / 1000),
            headers={
                "User-Agent": self.CHROME_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

        # Initialize Playwright browser
        if HAS_PLAYWRIGHT:
            try:
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
                logger.info("Playwright browser initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Playwright: {e}")

        # Initialize FlareSolverr client
        if self.flaresolverr_url:
            self.flaresolverr_client = httpx.AsyncClient(timeout=120)
            try:
                health_url = self.flaresolverr_url.replace("/v1", "/health")
                response = await self.flaresolverr_client.get(health_url)
                self.flaresolverr_available = response.status_code == 200
                if self.flaresolverr_available:
                    logger.info("FlareSolverr is available")
                else:
                    logger.warning("FlareSolverr health check failed")
            except Exception as e:
                logger.warning(f"FlareSolverr not available: {e}")

        # Initialize Zyte client
        from services.zyte import ZyteClient
        self.zyte_client = ZyteClient()
        if self.zyte_client.is_configured():
            await self.zyte_client.start()
            self.zyte_available = True
            logger.info("Zyte API client initialized")
        else:
            logger.info("Zyte API not configured (no ZYTE_API_KEY)")

        logger.info("SmartFetcher initialized")

    async def stop(self) -> None:
        """Cleanup resources."""
        if self.aiohttp_session:
            await self.aiohttp_session.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self.flaresolverr_client:
            await self.flaresolverr_client.aclose()
        if self.zyte_client:
            await self.zyte_client.stop()

    def _is_cloudflare(self, html: str) -> bool:
        """Check if response is Cloudflare challenge page."""
        html_lower = html.lower()
        return any(ind in html_lower for ind in self.CLOUDFLARE_INDICATORS)

    def _is_blocked_response(self, result: dict) -> bool:
        """Check if response indicates we're blocked (Cloudflare, 403, etc)."""
        html = result.get("html", "")
        status_code = result.get("status_code", 200)

        # Check for blocking status codes
        if status_code in [403, 401, 503, 429]:
            logger.warning(f"Blocked by status code: {status_code}")
            return True

        # Check for Cloudflare
        if self._is_cloudflare(html):
            logger.warning("Blocked by Cloudflare")
            return True

        # Check for common blocking page titles
        html_lower = html.lower()
        blocking_titles = [
            "<title>403 forbidden</title>",
            "<title>access denied</title>",
            "<title>blocked</title>",
            "<title>error</title>",
            "<title>just a moment</title>",
        ]
        if any(title in html_lower for title in blocking_titles):
            logger.warning("Blocked by error page title")
            return True

        return False

    def _build_translate_url(self, target_url: str, method: str = "website") -> str:
        """Build Google Translate proxy URL with cache-busting."""
        # Add cache-busting parameter to target URL
        cache_buster = f"_cb={int(time.time())}{random.randint(1000,9999)}"
        if "?" in target_url:
            busted_url = f"{target_url}&{cache_buster}"
        else:
            busted_url = f"{target_url}?{cache_buster}"

        if method == "website":
            params = {
                "sl": "auto",
                "tl": "en",
                "hl": "en",
                "u": busted_url
            }
            return f"{self.WEBSITE_URL}?{urlencode(params)}"
        else:
            params = {
                "sl": "auto",
                "tl": "en",
                "u": busted_url
            }
            return f"{self.TRANSLATE_URL}?{urlencode(params)}"

    def _clean_translated_html(self, html: str, original_url: str) -> str:
        """Clean Google Translate wrapper from HTML."""
        # Remove Google Translate toolbar/frame
        html = re.sub(r'<div[^>]*id="gt-nvframe"[^>]*>.*?</div>', '', html, flags=re.DOTALL)
        html = re.sub(r'<div[^>]*class="[^"]*goog-te-[^"]*"[^>]*>.*?</div>', '', html, flags=re.DOTALL)

        # Remove Google Translate scripts
        html = re.sub(r'<script[^>]*translate\.google[^>]*>.*?</script>', '', html, flags=re.DOTALL)

        # Fix translated URLs
        html = re.sub(
            r'https?://translate\.googleusercontent\.com/translate_c\?[^"\']*u=([^"\'&]+)',
            lambda m: m.group(1),
            html
        )

        return html

    async def _fetch_google_translate(self, url: str) -> dict:
        """
        Strategy 0: Fetch via Google Translate proxy.
        THE LOOPHOLE! Works on most blocked sites.
        """
        if not self.aiohttp_session:
            return {"success": False, "error": "Session not initialized"}

        start_time = time.time()

        for method in ["website", "translate"]:
            try:
                proxy_url = self._build_translate_url(url, method)
                logger.debug(f"[GoogleTranslate] Trying {method} method")

                async with self.aiohttp_session.get(proxy_url) as response:
                    if response.status == 200:
                        html = await response.text()

                        # Check for Cloudflare challenge
                        if self._is_cloudflare(html):
                            logger.warning(f"[GoogleTranslate] {method} got Cloudflare challenge")
                            continue

                        if len(html) > 1000 and "<html" in html.lower():
                            cleaned_html = self._clean_translated_html(html, url)
                            return {
                                "success": True,
                                "html": cleaned_html,
                                "status_code": 200,
                                "final_url": url,
                                "fetch_time_ms": int((time.time() - start_time) * 1000),
                                "strategy": "google_translate",
                            }

            except asyncio.TimeoutError:
                logger.warning(f"[GoogleTranslate] {method} timeout")
            except Exception as e:
                logger.warning(f"[GoogleTranslate] {method} error: {e}")

        return {
            "success": False,
            "error": "Google Translate proxy failed",
            "fetch_time_ms": int((time.time() - start_time) * 1000),
        }

    async def _fetch_with_ua(
        self,
        url: str,
        user_agent: str,
        use_stealth: bool = False,
        use_proxy: bool = False
    ) -> dict:
        """
        Fetch URL with Playwright browser and specific UA.

        Args:
            url: Target URL
            user_agent: User-Agent string
            use_stealth: Apply stealth patches
            use_proxy: Use proxy server
        """
        if not self.browser:
            return {"success": False, "error": "Browser not initialized"}

        context: Optional[BrowserContext] = None
        start_time = time.time()

        try:
            context_options = {
                "user_agent": user_agent,
                "viewport": {"width": 1920, "height": 1080},
                "locale": "en-US",
                "timezone_id": "America/New_York",
                "extra_http_headers": {
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            }

            if use_proxy and self.proxy_url:
                context_options["proxy"] = {"server": self.proxy_url}
                context_options["timezone_id"] = "Europe/Prague"

            context = await self.browser.new_context(**context_options)
            page = await context.new_page()

            if use_stealth and HAS_STEALTH:
                await stealth_async(page)

            # Add cache-busting to URL
            cache_buster = f"_cb={int(time.time())}{random.randint(1000,9999)}"
            busted_url = f"{url}&{cache_buster}" if "?" in url else f"{url}?{cache_buster}"

            response = await page.goto(busted_url, wait_until="domcontentloaded", timeout=self.timeout)

            if not response:
                return {"success": False, "error": "No response"}

            html = await page.content()

            # Wait for Cloudflare if detected
            if self._is_cloudflare(html):
                for _ in range(self.max_cf_wait):
                    await asyncio.sleep(1)
                    html = await page.content()
                    if not self._is_cloudflare(html):
                        break

                if self._is_cloudflare(html):
                    return {
                        "success": False,
                        "error": "Cloudflare challenge not resolved",
                        "cloudflare": True,
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
            if context:
                await context.close()

    async def _fetch_flaresolverr(self, url: str) -> dict:
        """
        Strategy 3: Fetch via FlareSolverr.
        For heavy Cloudflare protection.
        """
        if not self.flaresolverr_client or not self.flaresolverr_available:
            return {"success": False, "error": "FlareSolverr not available"}

        start_time = time.time()

        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 120000,
            "headers": {"User-Agent": self.GOOGLEBOT_UA}
        }

        try:
            response = await self.flaresolverr_client.post(
                self.flaresolverr_url,
                json=payload
            )
            data = response.json()

            if data.get("status") == "ok":
                solution = data.get("solution", {})
                return {
                    "success": True,
                    "html": solution.get("response", ""),
                    "status_code": solution.get("status", 200),
                    "final_url": solution.get("url"),
                    "fetch_time_ms": int((time.time() - start_time) * 1000),
                    "strategy": "flaresolverr",
                }
            else:
                return {
                    "success": False,
                    "error": data.get("message", "FlareSolverr request failed"),
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "fetch_time_ms": int((time.time() - start_time) * 1000),
            }

    async def fetch(self, url: str, skip_google_translate: bool = False) -> dict:
        """
        Smart fetch - tries multiple strategies.

        Args:
            url: URL to fetch
            skip_google_translate: Skip Google Translate strategy

        Returns:
            dict with success, html, status_code, final_url, strategy, etc.
        """
        start_time = time.time()

        # Strategy 0: Google Translate proxy (THE LOOPHOLE!)
        if not skip_google_translate:
            logger.info(f"[Strategy 0] Trying Google Translate for {url}")
            result = await self._fetch_google_translate(url)

            if result.get("success"):
                html = result.get("html", "")
                if not self._is_cloudflare(html) and len(html) > 500:
                    logger.info(f"[Strategy 0] SUCCESS via Google Translate")
                    return result

        # Strategy 1: Zyte API (for Cloudflare bypass - same as affiliate.fm!)
        if self.zyte_available:
            logger.info(f"[Strategy 1] Trying Zyte API for {url}")
            result = await self.zyte_client.fetch_html(url)

            if result.get("success"):
                html = result.get("html", "")
                if not self._is_cloudflare(html) and len(html) > 500:
                    logger.info(f"[Strategy 1] SUCCESS via Zyte API")
                    result["final_url"] = result.get("url", url)
                    return result

        # Strategy 2: Direct Googlebot UA
        if self.browser:
            logger.info(f"[Strategy 2] Trying direct Googlebot UA")
            result = await self._fetch_with_ua(url, self.GOOGLEBOT_UA, use_stealth=False)

            if result.get("success") and not self._is_blocked_response(result):
                result["strategy"] = "googlebot_direct"
                return result

            # Strategy 3: Googlebot UA with stealth
            logger.info(f"[Strategy 3] Trying Googlebot UA with stealth")
            result = await self._fetch_with_ua(url, self.GOOGLEBOT_UA, use_stealth=True)

            if result.get("success") and not self._is_blocked_response(result):
                result["strategy"] = "googlebot_stealth"
                return result

        # Strategy 4: FlareSolverr
        if self.flaresolverr_available:
            logger.info(f"[Strategy 4] Trying FlareSolverr")
            result = await self._fetch_flaresolverr(url)

            if result.get("success") and not self._is_blocked_response(result):
                return result

        # Strategy 5: Proxy fallback
        if self.proxy_url and self.browser:
            logger.info(f"[Strategy 5] Trying proxy fallback")
            result = await self._fetch_with_ua(
                url, self.GOOGLEBOT_UA, use_stealth=True, use_proxy=True
            )

            if result.get("success") and not self._is_cloudflare(result.get("html", "")):
                result["strategy"] = "proxy"
                return result

        # All strategies failed
        return {
            "success": False,
            "error": "All fetch strategies failed",
            "fetch_time_ms": int((time.time() - start_time) * 1000),
        }

    async def fetch_as_user(self, url: str) -> dict:
        """
        Fetch URL as regular Chrome user.
        Used for cloaking detection comparison.
        """
        if not self.browser:
            return {"success": False, "error": "Browser not initialized"}

        return await self._fetch_with_ua(url, self.CHROME_UA, use_stealth=True)


# Module-level instance
_fetcher: Optional[SmartFetcher] = None


async def get_fetcher() -> SmartFetcher:
    """Get or create SmartFetcher instance."""
    global _fetcher
    if _fetcher is None:
        _fetcher = SmartFetcher()
        await _fetcher.start()
    return _fetcher
