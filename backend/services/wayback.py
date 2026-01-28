"""
Wayback Machine Integration Service.
Fetches historical data from Internet Archive.
"""

import httpx
from typing import Optional
from datetime import datetime
from core.logging import get_logger

logger = get_logger(__name__)


class WaybackClient:
    """
    Wayback Machine API client for getting historical data.
    Provides first/last archive dates which can approximate indexing dates.
    """

    CDX_API_URL = "https://web.archive.org/cdx/search/cdx"
    AVAILABILITY_URL = "https://archive.org/wayback/available"

    def __init__(self, timeout: int = 30):
        """
        Initialize Wayback client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def start(self) -> None:
        """Initialize HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": "SEO-Pocket/1.0"}
            )
            logger.info("Wayback client initialized")

    async def stop(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _parse_timestamp(self, timestamp: str) -> Optional[str]:
        """Convert Wayback timestamp (YYYYMMDDHHMMSS) to ISO date."""
        try:
            dt = datetime.strptime(timestamp[:8], "%Y%m%d")
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    async def get_archive_dates(self, url: str) -> dict:
        """
        Get first and last archive dates for a URL.

        Args:
            url: URL to check

        Returns:
            dict with:
                - success: bool
                - first_archived: str (ISO date) or None
                - last_archived: str (ISO date) or None
                - total_snapshots: int
        """
        if not self._client:
            await self.start()

        result = {
            "success": False,
            "first_archived": None,
            "last_archived": None,
            "total_snapshots": 0
        }

        try:
            logger.info(f"Fetching Wayback dates for: {url}")

            # Get first snapshot
            first_response = await self._client.get(
                self.CDX_API_URL,
                params={
                    "url": url,
                    "limit": 1,
                    "output": "json",
                    "fl": "timestamp"
                }
            )

            logger.debug(f"First response status: {first_response.status_code}")
            if first_response.status_code == 200:
                try:
                    data = first_response.json()
                    if len(data) > 1:
                        # First row is headers, second is data
                        result["first_archived"] = self._parse_timestamp(data[1][0])
                        logger.info(f"First archived: {result['first_archived']}")
                except Exception as e:
                    logger.warning(f"Failed to parse first snapshot response: {e}")

            # Get last snapshot (reverse order)
            last_response = await self._client.get(
                self.CDX_API_URL,
                params={
                    "url": url,
                    "limit": 1,
                    "output": "json",
                    "fl": "timestamp",
                    "sort": "reverse"
                }
            )

            if last_response.status_code == 200:
                data = last_response.json()
                if len(data) > 1:
                    result["last_archived"] = self._parse_timestamp(data[1][0])

            # Get total count (approximate)
            count_response = await self._client.get(
                self.CDX_API_URL,
                params={
                    "url": url,
                    "output": "json",
                    "fl": "timestamp",
                    "showNumPages": "true"
                }
            )

            if count_response.status_code == 200:
                try:
                    # Response is just a number when showNumPages=true
                    result["total_snapshots"] = int(count_response.text.strip())
                except ValueError:
                    pass

            result["success"] = True
            logger.info(f"Wayback dates for {url}: first={result['first_archived']}, last={result['last_archived']}")

        except Exception as e:
            logger.error(f"Wayback API error: {e}")
            result["error"] = str(e)

        return result

    async def get_latest_snapshot_url(self, url: str) -> Optional[str]:
        """
        Get URL of the latest archived snapshot.

        Args:
            url: URL to check

        Returns:
            Wayback Machine URL or None
        """
        if not self._client:
            await self.start()

        try:
            response = await self._client.get(
                self.AVAILABILITY_URL,
                params={"url": url}
            )

            if response.status_code == 200:
                data = response.json()
                snapshot = data.get("archived_snapshots", {}).get("closest", {})
                if snapshot.get("available"):
                    return snapshot.get("url")

        except Exception as e:
            logger.error(f"Wayback availability error: {e}")

        return None
