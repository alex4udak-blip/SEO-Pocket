"""
FlareSolverr Client
Bypasses Cloudflare protection using FlareSolverr service
"""

import httpx
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# FlareSolverr endpoint
FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "http://localhost:8191/v1")


class FlareSolverrClient:
    """
    Client for FlareSolverr - a proxy server to bypass Cloudflare protection.
    https://github.com/FlareSolverr/FlareSolverr
    """

    def __init__(self, base_url: str = None, timeout: int = 60):
        self.base_url = base_url or FLARESOLVERR_URL
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None

    async def start(self):
        """Initialize HTTP client"""
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def stop(self):
        """Cleanup"""
        if self.client:
            await self.client.aclose()

    async def is_available(self) -> bool:
        """Check if FlareSolverr is running"""
        if not self.client:
            return False
        try:
            response = await self.client.get(self.base_url.replace("/v1", "/health"))
            return response.status_code == 200
        except Exception:
            return False

    async def fetch(self, url: str, googlebot_ua: bool = True) -> dict:
        """
        Fetch URL through FlareSolverr.

        Args:
            url: URL to fetch
            googlebot_ua: If True, use Googlebot User-Agent

        Returns:
            dict with success, html, status_code, error
        """
        if not self.client:
            return {"success": False, "error": "Client not initialized"}

        # Googlebot Mobile UA
        user_agent = (
            "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.184 Mobile Safari/537.36 "
            "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        ) if googlebot_ua else None

        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": self.timeout * 1000,
        }

        # Add custom headers if using Googlebot UA
        if user_agent:
            payload["headers"] = {"User-Agent": user_agent}

        try:
            response = await self.client.post(self.base_url, json=payload)
            data = response.json()

            if data.get("status") == "ok":
                solution = data.get("solution", {})
                return {
                    "success": True,
                    "html": solution.get("response", ""),
                    "status_code": solution.get("status", 200),
                    "final_url": solution.get("url"),
                    "cookies": solution.get("cookies", []),
                    "user_agent": solution.get("userAgent"),
                    "strategy": "flaresolverr",
                }
            else:
                return {
                    "success": False,
                    "error": data.get("message", "FlareSolverr request failed"),
                    "strategy": "flaresolverr",
                }

        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "FlareSolverr timeout",
                "strategy": "flaresolverr",
            }
        except Exception as e:
            logger.error(f"FlareSolverr error: {e}")
            return {
                "success": False,
                "error": str(e),
                "strategy": "flaresolverr",
            }


# Test
if __name__ == "__main__":
    import asyncio

    async def test():
        client = FlareSolverrClient()
        await client.start()

        available = await client.is_available()
        print(f"FlareSolverr available: {available}")

        if available:
            test_urls = [
                "https://paying-casinos-ca.it.com",
                "https://itworldcanada.com",
            ]

            for url in test_urls:
                print(f"\nTesting: {url}")
                result = await client.fetch(url)
                print(f"Success: {result.get('success')}")
                if result.get('success'):
                    html = result.get('html', '')
                    import re
                    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
                    if title_match:
                        print(f"Title: {title_match.group(1)}")
                else:
                    print(f"Error: {result.get('error')}")

        await client.stop()

    asyncio.run(test())
