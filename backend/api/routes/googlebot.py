"""
Googlebot View endpoint.
Returns raw HTML as seen by Googlebot or regular user.
"""

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse
from typing import Literal
from api.schemas import GooglebotViewResponse
from core.logging import get_logger

router = APIRouter(tags=["googlebot"])
logger = get_logger(__name__)

# Dependencies injected at startup
_fetcher = None
_cache = None


def set_dependencies(fetcher, cache):
    """Inject dependencies from main app."""
    global _fetcher, _cache
    _fetcher = fetcher
    _cache = cache


@router.get("/googlebot-view", response_model=GooglebotViewResponse)
async def googlebot_view(
    url: str = Query(..., description="URL to fetch"),
    mode: Literal["bot", "user"] = Query("bot", description="Fetch mode: bot or user"),
) -> GooglebotViewResponse:
    """
    Get HTML as seen by Googlebot or regular user.

    - **mode=bot**: HTML as Googlebot sees it (default)
    - **mode=user**: HTML as regular Chrome user sees it
    """
    if not _fetcher:
        raise HTTPException(status_code=503, detail="Fetcher not initialized")

    logger.info(f"Googlebot view request: url={url}, mode={mode}")

    try:
        if mode == "bot":
            result = await _fetcher.fetch(url)
        else:
            result = await _fetcher.fetch_as_user(url)

        if not result.get("success"):
            return GooglebotViewResponse(
                success=False,
                url=url,
                mode=mode,
                error=result.get("error", "Failed to fetch"),
                fetch_time_ms=result.get("fetch_time_ms", 0),
            )

        return GooglebotViewResponse(
            success=True,
            url=url,
            mode=mode,
            html=result.get("html"),
            fetch_time_ms=result.get("fetch_time_ms", 0),
            strategy=result.get("strategy"),
        )

    except Exception as e:
        logger.error(f"Googlebot view error: {e}")
        return GooglebotViewResponse(
            success=False,
            url=url,
            mode=mode,
            error=str(e),
        )


@router.get("/googlebot-view/raw", response_class=HTMLResponse)
async def googlebot_view_raw(
    url: str = Query(..., description="URL to fetch"),
    mode: Literal["bot", "user"] = Query("bot", description="Fetch mode: bot or user"),
) -> HTMLResponse:
    """
    Get raw HTML as seen by Googlebot or regular user.
    Returns HTML directly (not JSON).
    """
    if not _fetcher:
        raise HTTPException(status_code=503, detail="Fetcher not initialized")

    try:
        if mode == "bot":
            result = await _fetcher.fetch(url)
        else:
            result = await _fetcher.fetch_as_user(url)

        if not result.get("success"):
            raise HTTPException(
                status_code=502,
                detail=result.get("error", "Failed to fetch")
            )

        return HTMLResponse(content=result.get("html", ""), status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
