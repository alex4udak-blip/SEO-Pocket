"""
Googlebot Preview endpoint.
Returns Mobile + Desktop + User views with screenshots.
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.logging import get_logger
import asyncio

router = APIRouter(tags=["googlebot-preview"])
logger = get_logger(__name__)

# Dependencies injected at startup
_fetcher = None
_cache = None
_rich_results_scanner = None


class ViewData(BaseModel):
    """Data for a single view (mobile/desktop/user)."""
    html: Optional[str] = None
    title: Optional[str] = None
    canonical: Optional[str] = None
    screenshot_base64: Optional[str] = None
    fetch_time_ms: int = 0
    success: bool = False
    error: Optional[str] = None


class PreviewResponse(BaseModel):
    """Full preview response with all views."""
    success: bool
    url: str
    mobile: Optional[ViewData] = None
    desktop: Optional[ViewData] = None
    user: Optional[ViewData] = None
    total_time_ms: int = 0
    strategy: Optional[str] = None
    error: Optional[str] = None


def set_dependencies(fetcher, cache, rich_results_scanner=None):
    """Inject dependencies from main app."""
    global _fetcher, _cache, _rich_results_scanner
    _fetcher = fetcher
    _cache = cache
    _rich_results_scanner = rich_results_scanner


@router.get("/googlebot-preview", response_model=PreviewResponse)
async def googlebot_preview(
    url: str = Query(..., description="URL to preview"),
    include_user: bool = Query(True, description="Include user view for comparison"),
    include_screenshots: bool = Query(True, description="Include screenshots"),
) -> PreviewResponse:
    """
    Get Googlebot preview with Mobile, Desktop and User views.

    Uses Rich Results Test for authentic Googlebot rendering.
    """
    logger.info(f"Googlebot preview request: url={url}")

    import time
    start_time = time.time()

    try:
        mobile_data = None
        desktop_data = None
        user_data = None
        strategy = "rich_results_test"

        # Try Rich Results Scanner first (best quality)
        if _rich_results_scanner:
            try:
                logger.info("Using Rich Results Scanner for Mobile + Desktop...")

                # Run Rich Results scan (gets both mobile and desktop)
                scan_result = _rich_results_scanner.scan_both(url)

                if scan_result.mobile and scan_result.mobile.success:
                    mobile_data = ViewData(
                        html=scan_result.mobile.html,
                        title=scan_result.mobile.title,
                        canonical=scan_result.mobile.canonical,
                        screenshot_base64=scan_result.mobile.screenshot_base64 if include_screenshots else None,
                        fetch_time_ms=scan_result.mobile.scan_time_ms,
                        success=True,
                    )
                else:
                    mobile_data = ViewData(
                        success=False,
                        error=scan_result.mobile.error if scan_result.mobile else "Mobile scan failed",
                    )

                if scan_result.desktop and scan_result.desktop.success:
                    desktop_data = ViewData(
                        html=scan_result.desktop.html,
                        title=scan_result.desktop.title,
                        canonical=scan_result.desktop.canonical,
                        screenshot_base64=scan_result.desktop.screenshot_base64 if include_screenshots else None,
                        fetch_time_ms=scan_result.desktop.scan_time_ms,
                        success=True,
                    )
                else:
                    desktop_data = ViewData(
                        success=False,
                        error=scan_result.desktop.error if scan_result.desktop else "Desktop scan failed",
                    )

            except Exception as e:
                logger.error(f"Rich Results Scanner error: {e}")
                strategy = "fallback_fetcher"

        # Fallback to SmartFetcher if Rich Results not available
        if not mobile_data and _fetcher:
            logger.info("Falling back to SmartFetcher...")
            strategy = "smart_fetcher"

            bot_result = await _fetcher.fetch(url)

            if bot_result.get("success"):
                # Parse basic data
                from services.parser import HTMLParser
                parser = HTMLParser(bot_result.get("html", ""))
                parsed = parser.parse()

                # Use same data for both mobile and desktop (SmartFetcher doesn't differentiate)
                view_data = ViewData(
                    html=bot_result.get("html"),
                    title=parsed.get("title"),
                    canonical=parsed.get("canonical"),
                    screenshot_base64=None,  # SmartFetcher doesn't provide screenshots
                    fetch_time_ms=bot_result.get("fetch_time_ms", 0),
                    success=True,
                )
                mobile_data = view_data
                desktop_data = view_data
                strategy = bot_result.get("strategy", "unknown")
            else:
                error_msg = bot_result.get("error", "Fetch failed")
                mobile_data = ViewData(success=False, error=error_msg)
                desktop_data = ViewData(success=False, error=error_msg)

        # Get user view for comparison
        if include_user and _fetcher:
            logger.info("Fetching user view...")
            user_result = await _fetcher.fetch_as_user(url)

            if user_result.get("success"):
                from services.parser import HTMLParser
                parser = HTMLParser(user_result.get("html", ""))
                parsed = parser.parse()

                user_data = ViewData(
                    html=user_result.get("html"),
                    title=parsed.get("title"),
                    canonical=parsed.get("canonical"),
                    screenshot_base64=None,
                    fetch_time_ms=user_result.get("fetch_time_ms", 0),
                    success=True,
                )
            else:
                user_data = ViewData(
                    success=False,
                    error=user_result.get("error", "User fetch failed"),
                )

        total_time = int((time.time() - start_time) * 1000)

        return PreviewResponse(
            success=True,
            url=url,
            mobile=mobile_data,
            desktop=desktop_data,
            user=user_data,
            total_time_ms=total_time,
            strategy=strategy,
        )

    except Exception as e:
        logger.error(f"Preview error: {e}")
        total_time = int((time.time() - start_time) * 1000)
        return PreviewResponse(
            success=False,
            url=url,
            total_time_ms=total_time,
            error=str(e),
        )
