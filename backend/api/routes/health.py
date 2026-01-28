"""
Health check endpoint.
"""

from fastapi import APIRouter
from api.schemas import HealthResponse
from core.config import settings

router = APIRouter(tags=["health"])


# Dependencies injected at startup
_fetcher = None
_cache = None
_dataforseo = None


def set_dependencies(fetcher, cache, dataforseo):
    """Inject dependencies from main app."""
    global _fetcher, _cache, _dataforseo
    _fetcher = fetcher
    _cache = cache
    _dataforseo = dataforseo


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    Returns status of all services.
    """
    return HealthResponse(
        status="ok",
        fetcher_ready=_fetcher is not None,
        flaresolverr_available=_fetcher.flaresolverr_available if _fetcher else False,
        flaresolverr_url=settings.flaresolverr_url,
        proxy_configured=bool(settings.proxy_url),
        cache_type=_cache.cache_type if _cache else "none",
        dataforseo_configured=_dataforseo.is_configured() if _dataforseo else False,
    )
