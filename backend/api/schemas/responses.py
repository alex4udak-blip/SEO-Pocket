"""
Pydantic models for API responses.
Designed to match affiliate.fm response format.
"""

from typing import Optional
from pydantic import BaseModel, HttpUrl, Field


class HreflangEntry(BaseModel):
    """Single hreflang entry."""
    lang: str
    url: str


class SEOData(BaseModel):
    """SEO metadata extracted from HTML."""
    title: Optional[str] = None
    h1: Optional[str] = None
    description: Optional[str] = None
    canonical: Optional[str] = None
    html_lang: Optional[str] = None
    robots: Optional[str] = None
    hreflang: list[HreflangEntry] = Field(default_factory=list)


class CloakingData(BaseModel):
    """Cloaking detection results."""
    detected: bool = False
    bot_only_lines: int = 0
    user_only_lines: int = 0
    bot_only_elements: list[str] = Field(default_factory=list)
    user_only_elements: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    """
    Response for /api/analyze endpoint.
    Matches affiliate.fm format.
    """
    success: bool
    url: str
    final_url: Optional[str] = None
    redirects: list[str] = Field(default_factory=list)

    # SEO data from HTML
    seo_data: Optional[SEOData] = None

    # Google canonical (from DataForSEO or info:url)
    google_canonical: Optional[str] = None

    # Dates (from Wayback Machine / DataForSEO)
    first_indexed: Optional[str] = None  # First archive date
    last_indexed: Optional[str] = None   # Last archive date
    published: Optional[str] = None      # Page publish date if available

    # Related domains (from DataForSEO)
    related_domains: list[str] = Field(default_factory=list)

    # Alternate URLs (from HTML link rel=alternate)
    alternate_urls: list[str] = Field(default_factory=list)

    # Cloaking detection
    cloaking: Optional[CloakingData] = None

    # Fetch info
    fetch_time_ms: int = 0
    strategy: Optional[str] = None
    cached: bool = False
    is_cloaked_content: bool = False  # True if content was fetched via google-proxy (affiliate.fm)

    # Error info
    error: Optional[str] = None

    # Raw HTML (optional, for debugging)
    html: Optional[str] = None


class GooglebotViewResponse(BaseModel):
    """
    Response for /api/googlebot-view endpoint.
    Returns raw HTML.
    """
    success: bool
    url: str
    mode: str  # "bot" or "user"
    html: Optional[str] = None
    fetch_time_ms: int = 0
    strategy: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Response for /api/health endpoint."""
    status: str = "ok"
    fetcher_ready: bool = False
    flaresolverr_available: bool = False
    flaresolverr_url: Optional[str] = None
    proxy_configured: bool = False
    cache_type: str = "memory"
    dataforseo_configured: bool = False
