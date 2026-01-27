"""
DataForSEO Integration
Fetches indexed data from Google SERP via DataForSEO API
"""

import os
import time
import logging
import httpx
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DataForSEOClient:
    """
    DataForSEO API client for getting Google indexed data.
    Uses SERP API to search for specific URLs and extract metadata.
    """

    BASE_URL = "https://api.dataforseo.com/v3"

    def __init__(
        self,
        login: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 30
    ):
        self.login = login or os.getenv("DATAFORSEO_LOGIN")
        self.password = password or os.getenv("DATAFORSEO_PASSWORD")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

        if not self.login or not self.password:
            logger.warning("DataForSEO credentials not configured")

    async def start(self):
        """Initialize HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=(self.login, self.password),
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )

    async def stop(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_configured(self) -> bool:
        """Check if credentials are configured"""
        return bool(self.login and self.password)

    async def get_indexed_data(self, url: str) -> dict:
        """
        Get indexed data for a URL from Google SERP.

        Returns:
            - indexed: bool - whether URL appears in Google
            - indexed_title: str - title from SERP
            - indexed_description: str - description from SERP
            - indexed_url: str - actual indexed URL
            - serp_position: int - position in SERP
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "DataForSEO not configured",
                "indexed": False
            }

        if not self._client:
            await self.start()

        start_time = time.time()
        result = {
            "success": False,
            "indexed": False,
            "indexed_title": None,
            "indexed_description": None,
            "indexed_url": None,
            "serp_position": None,
            "fetch_time_ms": 0
        }

        try:
            # Use info: operator to find specific URL in Google
            # This returns the page if it's indexed
            parsed = urlparse(url)
            domain = parsed.netloc

            # Search for the exact URL using site: and the path
            # Or use info: operator
            search_query = f"info:{url}"

            payload = [{
                "keyword": search_query,
                "location_code": 2840,  # USA
                "language_code": "en",
                "device": "desktop"
            }]

            response = await self._client.post(
                f"{self.BASE_URL}/serp/google/organic/live/advanced",
                json=payload
            )

            data = response.json()

            if data.get("status_code") == 20000:
                tasks = data.get("tasks", [])
                if tasks and tasks[0].get("result"):
                    serp_result = tasks[0]["result"][0]
                    items = serp_result.get("items", [])

                    # Find organic result matching our domain
                    for item in items:
                        if item.get("type") == "organic":
                            item_domain = item.get("domain", "")
                            item_url = item.get("url", "")

                            # Check if this is our target URL
                            if domain in item_domain or domain in item_url:
                                result["success"] = True
                                result["indexed"] = True
                                result["indexed_title"] = item.get("title")
                                result["indexed_description"] = item.get("description")
                                result["indexed_url"] = item_url
                                result["serp_position"] = item.get("rank_absolute")
                                break

                    # If no match found but query worked
                    if not result["indexed"]:
                        result["success"] = True
                        result["indexed"] = False
            else:
                result["error"] = data.get("status_message", "API error")

        except Exception as e:
            logger.error(f"DataForSEO error: {e}")
            result["error"] = str(e)

        result["fetch_time_ms"] = int((time.time() - start_time) * 1000)
        return result

    async def get_site_overview(self, domain: str) -> dict:
        """
        Get overview of a domain's indexed pages.

        Uses site: operator to see how many pages are indexed.
        """
        if not self.is_configured():
            return {"success": False, "error": "DataForSEO not configured"}

        if not self._client:
            await self.start()

        start_time = time.time()
        result = {
            "success": False,
            "indexed_pages_count": None,
            "sample_pages": [],
            "fetch_time_ms": 0
        }

        try:
            payload = [{
                "keyword": f"site:{domain}",
                "location_code": 2840,
                "language_code": "en",
                "device": "desktop"
            }]

            response = await self._client.post(
                f"{self.BASE_URL}/serp/google/organic/live/advanced",
                json=payload
            )

            data = response.json()

            if data.get("status_code") == 20000:
                tasks = data.get("tasks", [])
                if tasks and tasks[0].get("result"):
                    serp_result = tasks[0]["result"][0]

                    result["success"] = True
                    result["indexed_pages_count"] = serp_result.get("se_results_count")

                    # Get sample pages
                    items = serp_result.get("items", [])
                    for item in items[:5]:
                        if item.get("type") == "organic":
                            result["sample_pages"].append({
                                "title": item.get("title"),
                                "url": item.get("url"),
                                "description": item.get("description")
                            })
            else:
                result["error"] = data.get("status_message", "API error")

        except Exception as e:
            logger.error(f"DataForSEO error: {e}")
            result["error"] = str(e)

        result["fetch_time_ms"] = int((time.time() - start_time) * 1000)
        return result


# Test
if __name__ == "__main__":
    import asyncio

    async def test():
        client = DataForSEOClient(
            login="alex4nikmst@gmail.com",
            password="a4a77d593a387187"
        )
        await client.start()

        # Test indexed data
        print("Testing info: query...")
        result = await client.get_indexed_data("https://example.com")
        print(f"Indexed: {result.get('indexed')}")
        print(f"Title: {result.get('indexed_title')}")
        print(f"Description: {result.get('indexed_description')}")
        print(f"Time: {result.get('fetch_time_ms')}ms")

        print("\nTesting site: query...")
        overview = await client.get_site_overview("example.com")
        print(f"Indexed pages: {overview.get('indexed_pages_count')}")
        print(f"Sample pages: {len(overview.get('sample_pages', []))}")

        await client.stop()

    asyncio.run(test())
