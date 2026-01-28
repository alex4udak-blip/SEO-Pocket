"""
HTML Cache Service.
In-memory cache with TTL, optionally backed by Redis.
"""

import time
import hashlib
from typing import Optional
from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__)

# Optional Redis import
try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


class HTMLCache:
    """
    HTML caching with TTL support.
    Uses in-memory dict by default, Redis if REDIS_URL is set.
    """

    def __init__(self, ttl: int = None):
        """
        Initialize cache.

        Args:
            ttl: Time-to-live in seconds (default from settings)
        """
        self.ttl = ttl or settings.cache_ttl
        self._memory_cache: dict[str, tuple[str, float]] = {}  # url_hash -> (html, timestamp)
        self._redis: Optional["redis.Redis"] = None
        self._use_redis = False

    async def start(self) -> None:
        """Initialize Redis connection if configured."""
        if settings.redis_url and HAS_REDIS:
            try:
                self._redis = redis.from_url(settings.redis_url)
                await self._redis.ping()
                self._use_redis = True
                logger.info("Redis cache initialized")
            except Exception as e:
                logger.warning(f"Redis connection failed, using memory cache: {e}")
                self._use_redis = False
        else:
            logger.info("Using in-memory cache")

    async def stop(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()

    def _hash_url(self, url: str) -> str:
        """Create cache key from URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:32]

    async def get(self, url: str) -> Optional[str]:
        """
        Get cached HTML for URL.

        Args:
            url: URL to look up

        Returns:
            Cached HTML or None if not found/expired
        """
        key = self._hash_url(url)

        if self._use_redis and self._redis:
            try:
                html = await self._redis.get(f"seo:html:{key}")
                if html:
                    logger.debug(f"Cache hit (Redis): {url}")
                    return html.decode() if isinstance(html, bytes) else html
            except Exception as e:
                logger.warning(f"Redis get error: {e}")

        # Fallback to memory cache
        if key in self._memory_cache:
            html, timestamp = self._memory_cache[key]
            if time.time() - timestamp < self.ttl:
                logger.debug(f"Cache hit (memory): {url}")
                return html
            else:
                # Expired
                del self._memory_cache[key]

        return None

    async def set(self, url: str, html: str) -> None:
        """
        Cache HTML for URL.

        Args:
            url: URL as cache key
            html: HTML content to cache
        """
        key = self._hash_url(url)

        if self._use_redis and self._redis:
            try:
                await self._redis.setex(f"seo:html:{key}", self.ttl, html)
                logger.debug(f"Cached in Redis: {url}")
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        # Always store in memory as fallback
        self._memory_cache[key] = (html, time.time())
        logger.debug(f"Cached in memory: {url}")

    async def is_cached(self, url: str) -> bool:
        """
        Check if URL is in cache.

        Args:
            url: URL to check

        Returns:
            True if cached and not expired
        """
        return await self.get(url) is not None

    def clear_memory(self) -> None:
        """Clear memory cache."""
        self._memory_cache.clear()
        logger.info("Memory cache cleared")

    @property
    def cache_type(self) -> str:
        """Return cache backend type."""
        return "redis" if self._use_redis else "memory"
