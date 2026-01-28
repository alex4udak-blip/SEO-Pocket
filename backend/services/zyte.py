"""
Zyte API Integration Service.
Fetches HTML content using Zyte's browser rendering to bypass anti-bot protection.
"""

import time
import base64
from typing import Optional
import httpx
from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__)


class ZyteClient:
    """
    Zyte API client for fetching pages with anti-bot bypass.
    Uses browser rendering to handle Cloudflare and similar protections.
    """

    BASE_URL = "https://api.zyte.com/v1/extract"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 60
    ):
        """
        Initialize Zyte client.

        Args:
            api_key: Zyte API key (from settings if not provided)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or getattr(settings, 'zyte_api_key', None)
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

        if not self.is_configured():
            logger.warning("Zyte API key not configured")

    async def start(self) -> None:
        """Initialize HTTP client."""
        if self._client is None and self.is_configured():
            # Zyte uses Basic Auth with API key as username, empty password
            auth = (self.api_key, "")
            self._client = httpx.AsyncClient(
                auth=auth,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            logger.info("Zyte client initialized")

    async def stop(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    async def fetch_html(
        self,
        url: str,
        browser_html: bool = True,
        javascript: bool = True,
        screenshot: bool = False
    ) -> dict:
        """
        Fetch HTML content from URL using Zyte API.

        Args:
            url: URL to fetch
            browser_html: Use browser rendering (handles JS, Cloudflare)
            javascript: Enable JavaScript execution
            screenshot: Also capture screenshot

        Returns:
            dict with:
                - success: bool
                - html: str (page HTML)
                - status_code: int
                - url: str (final URL after redirects)
                - screenshot: str (base64, if requested)
                - fetch_time_ms: int
                - error: str (if failed)
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Zyte API not configured",
                "html": None
            }

        if not self._client:
            await self.start()

        start_time = time.time()
        result = {
            "success": False,
            "html": None,
            "status_code": None,
            "url": url,
            "screenshot": None,
            "fetch_time_ms": 0,
            "strategy": "zyte"
        }

        try:
            payload = {
                "url": url,
                "browserHtml": browser_html,
            }

            if screenshot:
                payload["screenshot"] = True

            logger.info(f"Zyte: fetching {url}")

            response = await self._client.post(
                self.BASE_URL,
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                result["success"] = True
                result["html"] = data.get("browserHtml") or data.get("httpResponseBody")
                result["status_code"] = data.get("statusCode", 200)
                result["url"] = data.get("url", url)

                if screenshot and data.get("screenshot"):
                    result["screenshot"] = data["screenshot"]

                logger.info(f"Zyte: success for {url}, status={result['status_code']}")

            elif response.status_code == 401:
                result["error"] = "Zyte API: Invalid API key"
                logger.error("Zyte: Invalid API key")

            elif response.status_code == 422:
                # Validation error
                error_data = response.json()
                result["error"] = f"Zyte API validation error: {error_data}"
                logger.error(f"Zyte validation error: {error_data}")

            elif response.status_code == 520:
                # Target website error
                result["error"] = "Target website returned an error"
                result["status_code"] = 520
                logger.warning(f"Zyte: target error for {url}")

            else:
                result["error"] = f"Zyte API error: HTTP {response.status_code}"
                logger.error(f"Zyte error: HTTP {response.status_code}")

        except httpx.TimeoutException:
            result["error"] = "Zyte API timeout"
            logger.error(f"Zyte timeout for {url}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Zyte error: {e}")

        result["fetch_time_ms"] = int((time.time() - start_time) * 1000)
        return result

    async def fetch_with_googlebot_ua(self, url: str) -> dict:
        """
        Fetch page simulating Googlebot user agent.

        Note: Zyte's browserHtml already handles most anti-bot protections.
        This method is for compatibility with existing code structure.
        """
        return await self.fetch_html(url, browser_html=True)


# Module-level singleton
_client: Optional[ZyteClient] = None


def get_zyte_client() -> ZyteClient:
    """Get or create Zyte client instance."""
    global _client
    if _client is None:
        _client = ZyteClient()
    return _client
