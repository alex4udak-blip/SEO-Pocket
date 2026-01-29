"""
Affiliate.fm API Integration Service.

Uses affiliate.fm API to fetch REAL Googlebot content (cloaked pages).
Affiliate.fm uses google-proxy IPs (66.249.x.x) which sites trust as real Googlebot.

This gives us CLOAKED content - the actual content sites show to Googlebot,
unlike Zyte which only bypasses Cloudflare but shows user content.

API Endpoints:
- /googlebot-view - Fetch HTML as Googlebot sees it (cloaked!)
- /canonical - Get Google's canonical URL for a page
- /google-cache - Get Google's cached version of a page
"""

import time
from typing import Optional
import httpx
from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__)


class AffiliateFmClient:
    """
    Affiliate.fm API client for fetching Googlebot view of pages.

    This is the REAL Googlebot view - sites show cloaked content to these requests
    because affiliate.fm uses google-proxy IPs (66.249.x.x) that resolve to
    google-proxy-*.google.com via rDNS.

    Requires valid JWT token from Telegram authentication.
    """

    BASE_URL = "https://api.affiliate.fm"

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: int = 60
    ):
        """
        Initialize affiliate.fm client.

        Args:
            token: JWT token from Telegram auth (from settings if not provided)
            timeout: Request timeout in seconds
        """
        self.token = token or getattr(settings, 'affiliate_fm_token', None)
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

        if not self.is_configured():
            logger.warning("Affiliate.fm token not configured")

    async def start(self) -> None:
        """Initialize HTTP client."""
        if self._client is None and self.is_configured():
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.token}",
                }
            )
            logger.info("Affiliate.fm client initialized")

    async def stop(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_configured(self) -> bool:
        """Check if token is configured."""
        return bool(self.token)

    def update_token(self, token: str) -> None:
        """Update JWT token (for refresh)."""
        self.token = token
        if self._client:
            self._client.headers["Authorization"] = f"Bearer {token}"
        logger.info("Affiliate.fm token updated")

    async def fetch_googlebot_view(
        self,
        url: str,
        lang: str = "en"
    ) -> dict:
        """
        Fetch page as Googlebot sees it (cloaked content!).

        This is the REAL Googlebot view - sites show their cloaked content
        because affiliate.fm uses trusted google-proxy IPs.

        Args:
            url: URL to fetch
            lang: Language code (default: en)

        Returns:
            dict with:
                - success: bool
                - html: str (cloaked HTML content!)
                - status_code: int
                - url: str (final URL)
                - fetch_time_ms: int
                - is_cloaked: bool (always True for this service)
                - error: str (if failed)
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Affiliate.fm token not configured",
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
            "fetch_time_ms": 0,
            "strategy": "affiliate_fm",
            "is_cloaked": True,  # This service returns cloaked content!
        }

        try:
            endpoint = f"{self.BASE_URL}/googlebot-view"
            params = {"url": url, "lang": lang}

            logger.info(f"Affiliate.fm: fetching Googlebot view for {url}")

            response = await self._client.get(endpoint, params=params)

            if response.status_code == 200:
                # Response is HTML directly
                result["success"] = True
                result["html"] = response.text
                result["status_code"] = 200
                logger.info(f"Affiliate.fm: success for {url}, got {len(response.text)} chars")

            elif response.status_code == 401:
                result["error"] = "Affiliate.fm: Token expired or invalid"
                logger.error("Affiliate.fm: Token expired, needs refresh")

            elif response.status_code == 403:
                result["error"] = "Affiliate.fm: Subscription required"
                logger.error("Affiliate.fm: Subscription required for this URL")

            elif response.status_code == 429:
                result["error"] = "Affiliate.fm: Rate limit exceeded"
                logger.warning("Affiliate.fm: Rate limit hit")

            else:
                result["error"] = f"Affiliate.fm error: HTTP {response.status_code}"
                logger.error(f"Affiliate.fm error: HTTP {response.status_code}")

        except httpx.TimeoutException:
            result["error"] = "Affiliate.fm timeout"
            logger.error(f"Affiliate.fm timeout for {url}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Affiliate.fm error: {e}")

        result["fetch_time_ms"] = int((time.time() - start_time) * 1000)
        return result

    async def fetch_canonical(
        self,
        url: str,
        lang: str = "en"
    ) -> dict:
        """
        Get Google's canonical URL and indexing info for a page.

        Args:
            url: URL to check
            lang: Language code

        Returns:
            dict with:
                - success: bool
                - canonical: str (Google's canonical URL)
                - first_indexed: str (date)
                - last_indexed: str (date)
                - related_domains: list
                - error: str (if failed)
        """
        if not self.is_configured():
            return {"success": False, "error": "Token not configured"}

        if not self._client:
            await self.start()

        try:
            endpoint = f"{self.BASE_URL}/canonical"
            params = {"url": url, "lang": lang}

            response = await self._client.get(endpoint, params=params)

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "canonical": data.get("canonical"),
                    "first_indexed": data.get("firstIndexed"),
                    "last_indexed": data.get("lastIndexed"),
                    "related_domains": data.get("relatedDomains", []),
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def fetch_google_cache(
        self,
        url: str,
        lang: str = "en"
    ) -> dict:
        """
        Get Google's cached version of a page.

        Args:
            url: URL to get cache for
            lang: Language code

        Returns:
            dict with:
                - success: bool
                - html: str (cached HTML)
                - cache_date: str
                - error: str (if failed)
        """
        if not self.is_configured():
            return {"success": False, "error": "Token not configured"}

        if not self._client:
            await self.start()

        try:
            endpoint = f"{self.BASE_URL}/google-cache"
            params = {"url": url, "lang": lang}

            response = await self._client.get(endpoint, params=params)

            if response.status_code == 200:
                return {
                    "success": True,
                    "html": response.text,
                    "cache_date": response.headers.get("X-Cache-Date"),
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}


# Module-level singleton
_client: Optional[AffiliateFmClient] = None


def get_affiliate_fm_client() -> AffiliateFmClient:
    """Get or create affiliate.fm client instance."""
    global _client
    if _client is None:
        _client = AffiliateFmClient()
    return _client
