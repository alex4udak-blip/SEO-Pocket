"""
Configuration settings loaded from environment variables.
"""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # App
    app_name: str = "SEO-Pocket"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Fetcher
    fetch_timeout: int = 30000  # ms
    max_cloudflare_wait: int = 20  # seconds

    # FlareSolverr
    flaresolverr_url: Optional[str] = None

    # Proxy
    proxy_url: Optional[str] = None

    # DataForSEO
    dataforseo_login: Optional[str] = None
    dataforseo_password: Optional[str] = None

    # Zyte API (for Cloudflare bypass)
    zyte_api_key: Optional[str] = None

    # Affiliate.fm API (for REAL Googlebot view - cloaked content!)
    # Token from Telegram auth, stored in localStorage.tg_auth in browser
    affiliate_fm_token: Optional[str] = None

    # Redis (optional cache)
    redis_url: Optional[str] = None

    # Cache TTL
    cache_ttl: int = 3600  # 1 hour in seconds

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
