"""
Google Translate Website Proxy Service.

Uses Google Translate website proxy to fetch pages through google-proxy IPs.
This gives us CLOAKED content - the actual content sites show to Google crawlers,
because requests come from IP ranges like 66.249.x.x or 74.125.x.x with
rDNS resolving to google-proxy-*.google.com

Key insight: Sites trust based on IP + rDNS, not User-Agent!

URL Format:
  https://{domain-with-dashes}.translate.goog/{path}?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en

Example:
  https://example.com/page → https://example-com.translate.goog/page?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en
"""

import re
import time
from typing import Optional
from urllib.parse import urlparse, urlencode, parse_qs
import httpx
from core.logging import get_logger

logger = get_logger(__name__)


class GoogleTranslateProxy:
    """
    Google Translate Website Proxy for fetching cloaked content.

    Uses translate.goog domain which routes through google-proxy IPs.
    These IPs have rDNS like google-proxy-74-125-210-169.google.com
    which sites trust as legitimate Google traffic.
    """

    # Chrome User-Agent (Googlebot UA is blocked by Google Translate)
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # Google Translate params
    TRANSLATE_PARAMS = {
        "_x_tr_sl": "auto",  # Source language: auto-detect
        "_x_tr_tl": "en",    # Target language: English
        "_x_tr_hl": "en",    # UI language: English
    }

    # Patterns to clean Google Translate wrapper
    CLEANUP_PATTERNS = [
        # Google Translate navigation UI
        (r'<script[^>]*src="[^"]*gstatic\.com/_/translate_http/[^"]*"[^>]*></script>', ''),
        (r'<link[^>]*href="[^"]*gstatic\.com/_/translate_http/[^"]*"[^>]*>', ''),
        # Google Translate meta tags
        (r'<meta http-equiv="X-Translated-By"[^>]*>', ''),
        (r'<meta http-equiv="X-Translated-To"[^>]*>', ''),
        (r'<meta name="robots" content="none">', ''),
        # Google fonts for translate UI
        (r'<link[^>]*href="[^"]*fonts\.googleapis\.com[^"]*"[^>]*>', ''),
        # Inline translate scripts
        (r'<script[^>]*>.*?gtElInit.*?</script>', '', re.DOTALL),
        (r'<script id="google-translate-element-script"[^>]*>.*?</script>', '', re.DOTALL),
    ]

    def __init__(self, timeout: int = 30):
        """
        Initialize Google Translate proxy.

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
                headers={
                    "User-Agent": self.USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                follow_redirects=True,
            )
            logger.info("Google Translate proxy client initialized")

    async def stop(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_translate_url(self, url: str) -> str:
        """
        Convert regular URL to Google Translate proxy URL.

        Args:
            url: Original URL (e.g., https://example.com/page?q=test)

        Returns:
            Translate proxy URL (e.g., https://example-com.translate.goog/page?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en&q=test)
        """
        parsed = urlparse(url)

        # Convert domain: example.com → example-com
        domain_with_dashes = parsed.netloc.replace(".", "-")

        # Build path
        path = parsed.path or "/"

        # Combine translate params with original query params
        params = dict(self.TRANSLATE_PARAMS)
        if parsed.query:
            original_params = parse_qs(parsed.query)
            for key, values in original_params.items():
                params[key] = values[0] if len(values) == 1 else values

        # Build final URL
        translate_url = f"https://{domain_with_dashes}.translate.goog{path}"
        if params:
            translate_url += "?" + urlencode(params, doseq=True)

        return translate_url

    def _rewrite_links(self, html: str, original_domain: str) -> str:
        """
        Rewrite translate.goog links back to original domain.

        Args:
            html: HTML with translate.goog links
            original_domain: Original domain (e.g., example.com)

        Returns:
            HTML with original domain links
        """
        domain_with_dashes = original_domain.replace(".", "-")

        # Rewrite href/src attributes
        html = re.sub(
            rf'(href|src)="https://{domain_with_dashes}\.translate\.goog([^"]*)\?[^"]*_x_tr[^"]*"',
            rf'\1="https://{original_domain}\2"',
            html
        )

        # Rewrite inline URLs
        html = html.replace(f"{domain_with_dashes}.translate.goog", original_domain)

        return html

    def _cleanup_html(self, html: str) -> str:
        """
        Remove Google Translate wrapper elements.

        Args:
            html: Raw HTML from translate.goog

        Returns:
            Cleaned HTML
        """
        for pattern in self.CLEANUP_PATTERNS:
            if len(pattern) == 2:
                html = re.sub(pattern[0], pattern[1], html, flags=re.IGNORECASE)
            else:
                html = re.sub(pattern[0], pattern[1], html, flags=re.IGNORECASE | pattern[2])

        return html

    async def fetch(self, url: str, cleanup: bool = True) -> dict:
        """
        Fetch URL through Google Translate proxy.

        This routes the request through Google's infrastructure,
        giving us a google-proxy IP that sites trust.

        Args:
            url: URL to fetch
            cleanup: Whether to clean Google Translate wrapper

        Returns:
            dict with:
                - success: bool
                - html: str (cloaked content!)
                - status_code: int
                - url: str (original URL)
                - translate_url: str (proxy URL used)
                - fetch_time_ms: int
                - strategy: str = "google_translate"
                - is_cloaked: bool (True - this returns cloaked content)
                - error: str (if failed)
        """
        if not self._client:
            await self.start()

        start_time = time.time()
        parsed = urlparse(url)
        translate_url = self._build_translate_url(url)

        result = {
            "success": False,
            "html": None,
            "status_code": None,
            "url": url,
            "translate_url": translate_url,
            "fetch_time_ms": 0,
            "strategy": "google_translate",
            "is_cloaked": True,  # This service returns cloaked content!
        }

        try:
            logger.info(f"Google Translate proxy: fetching {url}")
            logger.debug(f"Translate URL: {translate_url}")

            response = await self._client.get(translate_url)
            result["status_code"] = response.status_code

            if response.status_code == 200:
                html = response.text

                # Check for Google Translate error page
                if "Can&#39;t reach this website" in html or "Can't reach this website" in html:
                    result["error"] = "Google Translate cannot reach the website"
                    logger.warning(f"Google Translate blocked for {url}")
                else:
                    # Clean up Google Translate wrapper
                    if cleanup:
                        html = self._cleanup_html(html)
                        html = self._rewrite_links(html, parsed.netloc)

                    result["success"] = True
                    result["html"] = html
                    logger.info(f"Google Translate proxy: success for {url}, got {len(html)} chars")

            else:
                result["error"] = f"HTTP {response.status_code}"
                logger.error(f"Google Translate proxy error: HTTP {response.status_code}")

        except httpx.TimeoutException:
            result["error"] = "Timeout"
            logger.error(f"Google Translate proxy timeout for {url}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Google Translate proxy error: {e}")

        result["fetch_time_ms"] = int((time.time() - start_time) * 1000)
        return result

    async def check_cloaking(self, url: str) -> dict:
        """
        Quick check if a URL returns different content via Google proxy.

        Looks for tell-tale signs of cloaking like fresh dates.

        Args:
            url: URL to check

        Returns:
            dict with:
                - has_fresh_dates: bool (2025-2026 dates found)
                - date_mentions: list of found dates
                - likely_cloaked: bool
        """
        result = await self.fetch(url)

        if not result["success"]:
            return {
                "has_fresh_dates": False,
                "date_mentions": [],
                "likely_cloaked": False,
                "error": result.get("error"),
            }

        html = result["html"]

        # Look for recent dates (signs of fresh/cloaked content)
        date_pattern = r'202[5-6]|January 202[5-6]|February 202[5-6]|March 202[5-6]'
        dates = re.findall(date_pattern, html, re.IGNORECASE)

        return {
            "has_fresh_dates": len(dates) > 0,
            "date_mentions": dates[:10],  # Limit to 10
            "likely_cloaked": len(dates) > 3,
        }


# Module-level singleton
_proxy: Optional[GoogleTranslateProxy] = None


def get_google_translate_proxy() -> GoogleTranslateProxy:
    """Get or create Google Translate proxy instance."""
    global _proxy
    if _proxy is None:
        _proxy = GoogleTranslateProxy()
    return _proxy
