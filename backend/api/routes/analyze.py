"""
Analyze endpoint.
Main SEO analysis with cloaking detection.
"""

from fastapi import APIRouter, Query, HTTPException, Body
from pydantic import BaseModel, HttpUrl
from typing import Optional
from api.schemas import AnalyzeResponse, SEOData, CloakingData, HreflangEntry
from services.parser import HTMLParser
from services.cloaking import CloakingDetector
from core.logging import get_logger

router = APIRouter(tags=["analyze"])
logger = get_logger(__name__)

# Dependencies injected at startup
_fetcher = None
_cache = None
_dataforseo = None
_wayback = None
_cloaking_detector = None


class AnalyzeRequest(BaseModel):
    """Request body for POST /api/analyze"""
    url: str
    detect_cloaking: bool = False
    include_html: bool = False


def set_dependencies(fetcher, cache, dataforseo, wayback=None):
    """Inject dependencies from main app."""
    global _fetcher, _cache, _dataforseo, _wayback, _cloaking_detector
    _fetcher = fetcher
    _cache = cache
    _dataforseo = dataforseo
    _wayback = wayback
    _cloaking_detector = CloakingDetector()


@router.get("/analyze", response_model=AnalyzeResponse)
async def analyze_url_get(
    url: str = Query(..., description="URL to analyze"),
    detect_cloaking: bool = Query(False, description="Enable cloaking detection"),
    include_html: bool = Query(False, description="Include raw HTML in response"),
) -> AnalyzeResponse:
    """GET endpoint - accepts query parameters."""
    return await _analyze(url, detect_cloaking, include_html)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_url_post(
    request: AnalyzeRequest,
) -> AnalyzeResponse:
    """POST endpoint - accepts JSON body."""
    return await _analyze(request.url, request.detect_cloaking, request.include_html)


async def _analyze(
    url: str,
    detect_cloaking: bool = False,
    include_html: bool = False,
) -> AnalyzeResponse:
    """
    Analyze URL and extract SEO data.

    Returns:
    - SEO metadata (title, h1, description, canonical, robots, hreflang)
    - Google canonical (from DataForSEO)
    - Cloaking detection (optional)
    - Fetch strategy used
    """
    if not _fetcher:
        raise HTTPException(status_code=503, detail="Fetcher not initialized")

    logger.info(f"Analyze request: url={url}, cloaking={detect_cloaking}")

    # Check cache first
    cached_html = None
    if _cache:
        cached_html = await _cache.get(url)

    try:
        # Fetch as Googlebot
        if cached_html:
            bot_result = {
                "success": True,
                "html": cached_html,
                "strategy": "cached",
                "fetch_time_ms": 0,
            }
        else:
            bot_result = await _fetcher.fetch(url)

            # Cache successful fetch
            if bot_result.get("success") and _cache:
                await _cache.set(url, bot_result.get("html", ""))

        if not bot_result.get("success"):
            return AnalyzeResponse(
                success=False,
                url=url,
                error=bot_result.get("error", "Failed to fetch"),
                fetch_time_ms=bot_result.get("fetch_time_ms", 0),
            )

        bot_html = bot_result.get("html", "")

        # Parse SEO data
        parser = HTMLParser(bot_html)
        parsed = parser.parse()

        seo_data = SEOData(
            title=parsed.get("title"),
            h1=parsed.get("h1"),
            description=parsed.get("description"),
            canonical=parsed.get("canonical"),
            html_lang=parsed.get("html_lang"),
            robots=parsed.get("robots"),
            hreflang=[
                HreflangEntry(lang=h.get("lang", ""), url=h.get("url", ""))
                for h in parsed.get("hreflang", [])
            ],
        )

        # Cloaking detection (optional)
        cloaking_data = None
        if detect_cloaking and _cloaking_detector:
            logger.info("Running cloaking detection...")
            user_result = await _fetcher.fetch_as_user(url)

            if user_result.get("success"):
                user_html = user_result.get("html", "")
                cloaking_result = _cloaking_detector.compare(bot_html, user_html)
                cloaking_data = CloakingData(
                    detected=cloaking_result.detected,
                    bot_only_lines=cloaking_result.bot_only_lines,
                    user_only_lines=cloaking_result.user_only_lines,
                    bot_only_elements=cloaking_result.bot_only_elements,
                    user_only_elements=cloaking_result.user_only_elements,
                )

        # Get Google canonical from DataForSEO
        google_canonical = None
        if _dataforseo and _dataforseo.is_configured():
            try:
                google_canonical = await _dataforseo.get_google_canonical(url)
            except Exception as e:
                logger.warning(f"DataForSEO error: {e}")

        # Get archive dates from Wayback Machine
        first_indexed = None
        last_indexed = None
        if _wayback:
            try:
                wayback_data = await _wayback.get_archive_dates(url)
                if wayback_data.get("success"):
                    first_indexed = wayback_data.get("first_archived")
                    last_indexed = wayback_data.get("last_archived")
            except Exception as e:
                logger.warning(f"Wayback error: {e}")

        # Build response
        redirects = []
        final_url = bot_result.get("final_url")
        if final_url and final_url != url:
            redirects.append(f"{url} -> {final_url}")

        # Get alternate URLs from parsed data
        alternate_urls = parsed.get("alternate_urls", [])

        return AnalyzeResponse(
            success=True,
            url=url,
            final_url=final_url or url,
            redirects=redirects,
            seo_data=seo_data,
            google_canonical=google_canonical,
            first_indexed=first_indexed,
            last_indexed=last_indexed,
            alternate_urls=alternate_urls,
            cloaking=cloaking_data,
            fetch_time_ms=bot_result.get("fetch_time_ms", 0),
            strategy=bot_result.get("strategy"),
            cached=cached_html is not None,
            html=bot_html if include_html else None,
        )

    except Exception as e:
        logger.error(f"Analyze error: {e}")
        return AnalyzeResponse(
            success=False,
            url=url,
            error=str(e),
        )
