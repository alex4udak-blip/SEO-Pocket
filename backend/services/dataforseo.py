"""
DataForSEO Integration Service.
Fetches indexed data from Google SERP via DataForSEO API.
"""

import time
from typing import Optional
from urllib.parse import urlparse
import httpx
from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__)


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
        """
        Initialize DataForSEO client.

        Args:
            login: DataForSEO login (from settings if not provided)
            password: DataForSEO password (from settings if not provided)
            timeout: Request timeout in seconds
        """
        self.login = login or settings.dataforseo_login
        self.password = password or settings.dataforseo_password
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

        if not self.is_configured():
            logger.warning("DataForSEO credentials not configured")

    async def start(self) -> None:
        """Initialize HTTP client."""
        if self._client is None and self.is_configured():
            self._client = httpx.AsyncClient(
                auth=(self.login, self.password),
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            logger.info("DataForSEO client initialized")

    async def stop(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_configured(self) -> bool:
        """Check if credentials are configured."""
        return bool(self.login and self.password)

    async def get_indexed_data(self, url: str) -> dict:
        """
        Get indexed data for a URL from Google SERP.

        Args:
            url: URL to check

        Returns:
            dict with:
                - success: bool
                - indexed: bool
                - indexed_title: str
                - indexed_description: str
                - indexed_url: str (Google canonical)
                - serp_position: int
                - is_fallback: bool (True if found via site: instead of info:)
        """
        logger.info(f"get_indexed_data called for: {url}")
        logger.info(f"is_configured: {self.is_configured()}")

        if not self.is_configured():
            logger.warning("DataForSEO not configured - missing credentials")
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
            "is_fallback": False,
            "fetch_time_ms": 0
        }

        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")

        # Known SLD (Second Level Domains) that should be treated as TLDs
        sld_list = {
            'co.uk', 'co.nz', 'co.jp', 'co.kr', 'co.il', 'co.in', 'co.za',
            'com.au', 'com.br', 'com.mx', 'com.ar', 'com.tr', 'com.ua',
            'org.uk', 'org.au', 'net.au', 'gov.uk', 'ac.uk',
            'it.com', 'us.com', 'eu.com', 'de.com', 'ru.com',  # .it.com etc
        }

        # Extract base domain for comparison (handle subdomains)
        domain_parts = domain.split('.')

        # Check if last 2 parts form an SLD
        if len(domain_parts) >= 2:
            potential_sld = '.'.join(domain_parts[-2:])
            if potential_sld in sld_list:
                # Use last 3 parts as base domain
                base_domain = '.'.join(domain_parts[-3:]) if len(domain_parts) > 2 else domain
                is_subdomain = len(domain_parts) > 3
            else:
                base_domain = '.'.join(domain_parts[-2:]) if len(domain_parts) > 2 else domain
                is_subdomain = len(domain_parts) > 2
        else:
            base_domain = domain
            is_subdomain = False

        logger.info(f"Domain analysis: domain={domain}, base_domain={base_domain}, is_subdomain={is_subdomain}")

        try:
            # Step 1: Try info: operator first (exact URL match)
            search_query = f"info:{url}"
            logger.info(f"Trying info: query for: {url}")

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
            logger.info(f"DataForSEO info: response status_code: {data.get('status_code')}")

            if data.get("status_code") == 20000:
                tasks = data.get("tasks", [])
                if tasks and tasks[0].get("result"):
                    serp_result = tasks[0]["result"][0]
                    items = serp_result.get("items", [])
                    logger.info(f"DataForSEO info: found {len(items)} items")

                    # Find organic result matching our domain EXACTLY
                    for item in items:
                        if item.get("type") == "organic":
                            item_domain = item.get("domain", "").lower().replace("www.", "")
                            item_url = item.get("url", "")

                            # Strip www from our domains for comparison
                            clean_domain = domain.lower().replace("www.", "")
                            clean_base = base_domain.lower()

                            # STRICT match: item domain must BE or END WITH our domain
                            is_exact_match = (
                                item_domain == clean_domain or
                                item_domain == clean_base or
                                item_domain.endswith("." + clean_domain) or
                                item_domain.endswith("." + clean_base)
                            )

                            if is_exact_match:
                                result["success"] = True
                                result["indexed"] = True
                                result["indexed_title"] = item.get("title")
                                result["indexed_description"] = item.get("description")
                                result["indexed_url"] = item_url
                                result["serp_position"] = item.get("rank_absolute")
                                logger.info(f"DataForSEO info: matched: indexed_url={item_url}")
                                break

            # Step 2: If info: didn't find anything, try site: for base domain
            if not result["indexed"] and is_subdomain:
                logger.info(f"info: didn't find result, trying site: for base domain: {base_domain}")

                site_query = f"site:{base_domain}"
                payload = [{
                    "keyword": site_query,
                    "location_code": 2840,
                    "language_code": "en",
                    "device": "desktop"
                }]

                response = await self._client.post(
                    f"{self.BASE_URL}/serp/google/organic/live/advanced",
                    json=payload
                )

                data = response.json()
                logger.info(f"DataForSEO site: response status_code: {data.get('status_code')}")

                if data.get("status_code") == 20000:
                    tasks = data.get("tasks", [])
                    if tasks and tasks[0].get("result"):
                        serp_result = tasks[0]["result"][0]
                        items = serp_result.get("items", [])
                        logger.info(f"DataForSEO site: found {len(items)} items")

                        # Take first organic result that matches base domain as Google canonical
                        for item in items:
                            if item.get("type") == "organic":
                                item_domain = item.get("domain", "").lower().replace("www.", "")
                                clean_base = base_domain.lower()

                                # Only accept if item domain matches our base domain
                                is_base_match = (
                                    item_domain == clean_base or
                                    item_domain.endswith("." + clean_base)
                                )

                                if is_base_match:
                                    result["success"] = True
                                    result["indexed"] = True
                                    result["indexed_title"] = item.get("title")
                                    result["indexed_description"] = item.get("description")
                                    result["indexed_url"] = item.get("url")
                                    result["serp_position"] = item.get("rank_absolute")
                                    result["is_fallback"] = True  # Mark as fallback
                                    logger.info(f"DataForSEO site: fallback matched: indexed_url={item.get('url')}")
                                    break

            if not result["indexed"]:
                result["success"] = True
                result["indexed"] = False
                logger.info(f"DataForSEO: URL not found in SERP results")

        except Exception as e:
            logger.error(f"DataForSEO error: {e}")
            result["error"] = str(e)

        result["fetch_time_ms"] = int((time.time() - start_time) * 1000)
        return result

    async def get_google_canonical(self, url: str) -> Optional[str]:
        """
        Get Google's canonical URL for a page.

        Args:
            url: URL to check

        Returns:
            Google's canonical URL or None
        """
        data = await self.get_indexed_data(url)
        return data.get("indexed_url") if data.get("indexed") else None

    async def get_site_overview(self, domain: str) -> dict:
        """
        Get overview of a domain's indexed pages.

        Args:
            domain: Domain to check

        Returns:
            dict with indexed_pages_count and sample_pages
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
