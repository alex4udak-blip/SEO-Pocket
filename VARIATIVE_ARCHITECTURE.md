# SEO-Pocket — Вариативная архитектура с fallback источниками

## Проблема

Любой единственный источник данных — это single point of failure:
- Google может изменить интерфейс Rich Results Test
- Rate limiting
- CAPTCHA
- Блокировка IP

## Решение: Multi-Source Strategy с автоматическим fallback

```
┌─────────────────────────────────────────────────────────────────┐
│                     SEO-Pocket Backend                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                   Source Manager                          │  │
│   │   (Выбирает источник, управляет fallback)                 │  │
│   └──────────────────────────────────────────────────────────┘  │
│                            │                                     │
│         ┌──────────────────┼──────────────────┐                 │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐             │
│   │ Source 1 │      │ Source 2 │      │ Source 3 │             │
│   │ Primary  │ ──▶  │ Fallback │ ──▶  │ Fallback │             │
│   │          │      │    #1    │      │    #2    │             │
│   └──────────┘      └──────────┘      └──────────┘             │
│                                                                  │
│   Priority: 1. Rich Results  2. Google Cache  3. Direct+UA      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Источники данных (по приоритету)

### Source 1: Google Rich Results Test (PRIMARY)
**Как работает:**
1. Playwright открывает search.google.com/test/rich-results
2. Вводит URL, ждёт результат
3. Кликает "Посмотреть проверенную страницу"
4. Извлекает rendered HTML

**Плюсы:**
- Реальный Googlebot рендер
- Точные данные

**Минусы:**
- Медленно (10-20 сек)
- Может сломаться при изменении UI
- Rate limiting

**Health check:**
```python
async def check_rich_results_health():
    try:
        result = await fetch_via_rich_results("https://example.com")
        return "Example Domain" in result
    except:
        return False
```

### Source 2: Google Cache Scraping (FALLBACK #1)
**Как работает:**
1. Запрос к webcache.googleusercontent.com
2. Парсинг HTML из кэша

**Плюсы:**
- Быстрее чем Rich Results
- Реальные данные от Google

**Минусы:**
- Не все страницы закэшированы
- Кэш может быть устаревшим
- noarchive блокирует

**Health check:**
```python
async def check_google_cache_health():
    try:
        result = await fetch_via_google_cache("https://example.com")
        return len(result) > 100
    except:
        return False
```

### Source 3: Direct Fetch + Googlebot UA (FALLBACK #2)
**Как работает:**
1. Playwright с Googlebot User-Agent
2. Рендер JavaScript
3. Извлечение HTML

**Плюсы:**
- Полный контроль
- Быстро
- Не зависит от Google сервисов

**Минусы:**
- Сайты могут проверять IP
- Не 100% идентично Googlebot
- Некоторые сайты блокируют

**User-Agent:**
```
Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/W.X.Y.Z Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)
```

### Source 4: Wayback Machine (FALLBACK #3)
**Как работает:**
1. Запрос к web.archive.org API
2. Получение последнего снапшота

**Плюсы:**
- Исторические данные
- Стабильный API

**Минусы:**
- Может быть очень устаревшим
- Не все сайты архивируются

---

## Код: Source Manager

```python
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
import asyncio
import logging

logger = logging.getLogger(__name__)

class SourceType(Enum):
    RICH_RESULTS = "rich_results"
    GOOGLE_CACHE = "google_cache"
    DIRECT_GOOGLEBOT = "direct_googlebot"
    WAYBACK = "wayback"

@dataclass
class SourceResult:
    success: bool
    html: Optional[str]
    source: SourceType
    error: Optional[str] = None
    cached: bool = False
    fetch_time_ms: int = 0

@dataclass
class SourceHealth:
    source: SourceType
    healthy: bool
    last_check: float
    consecutive_failures: int = 0

class SourceManager:
    """
    Manages multiple HTML sources with automatic fallback.
    """

    def __init__(self):
        self.sources = [
            SourceType.RICH_RESULTS,
            SourceType.GOOGLE_CACHE,
            SourceType.DIRECT_GOOGLEBOT,
            SourceType.WAYBACK,
        ]
        self.health: Dict[SourceType, SourceHealth] = {}
        self.fetchers: Dict[SourceType, callable] = {}

    def register_fetcher(self, source: SourceType, fetcher: callable):
        """Register a fetcher function for a source type."""
        self.fetchers[source] = fetcher

    async def fetch(self, url: str) -> SourceResult:
        """
        Fetch URL using available sources with automatic fallback.
        """
        for source in self.sources:
            # Skip unhealthy sources
            if not self._is_source_healthy(source):
                logger.warning(f"Skipping unhealthy source: {source.value}")
                continue

            try:
                fetcher = self.fetchers.get(source)
                if not fetcher:
                    continue

                start_time = asyncio.get_event_loop().time()
                html = await fetcher(url)
                fetch_time = int((asyncio.get_event_loop().time() - start_time) * 1000)

                if html and len(html) > 100:
                    self._mark_success(source)
                    return SourceResult(
                        success=True,
                        html=html,
                        source=source,
                        fetch_time_ms=fetch_time
                    )

            except Exception as e:
                logger.error(f"Source {source.value} failed: {e}")
                self._mark_failure(source)
                continue

        return SourceResult(
            success=False,
            html=None,
            source=SourceType.RICH_RESULTS,
            error="All sources failed"
        )

    def _is_source_healthy(self, source: SourceType) -> bool:
        """Check if source is healthy based on recent failures."""
        health = self.health.get(source)
        if not health:
            return True  # Unknown = assume healthy
        return health.consecutive_failures < 3

    def _mark_success(self, source: SourceType):
        """Mark source as successful."""
        self.health[source] = SourceHealth(
            source=source,
            healthy=True,
            last_check=asyncio.get_event_loop().time(),
            consecutive_failures=0
        )

    def _mark_failure(self, source: SourceType):
        """Mark source as failed."""
        current = self.health.get(source)
        failures = (current.consecutive_failures + 1) if current else 1
        self.health[source] = SourceHealth(
            source=source,
            healthy=failures < 3,
            last_check=asyncio.get_event_loop().time(),
            consecutive_failures=failures
        )
```

---

## Код: Individual Fetchers

### Rich Results Fetcher

```python
from playwright.async_api import async_playwright
import asyncio

class RichResultsFetcher:
    """Fetches HTML via Google Rich Results Test."""

    async def fetch(self, url: str, timeout: int = 30000) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720}
            )
            page = await context.new_page()

            try:
                # Navigate to Rich Results Test
                await page.goto(
                    f"https://search.google.com/test/rich-results?url={url}",
                    wait_until="networkidle",
                    timeout=timeout
                )

                # Wait for results
                await page.wait_for_selector(
                    'text="Посмотреть проверенную страницу"',
                    timeout=timeout
                )

                # Click to view HTML
                await page.click('text="Посмотреть проверенную страницу"')

                # Wait for HTML panel
                await page.wait_for_selector('.html-content', timeout=10000)

                # Extract HTML
                html = await page.evaluate('''
                    () => {
                        const panel = document.querySelector('.html-content');
                        return panel ? panel.textContent : null;
                    }
                ''')

                return html

            finally:
                await browser.close()
```

### Google Cache Fetcher

```python
import httpx

class GoogleCacheFetcher:
    """Fetches HTML from Google Cache."""

    async def fetch(self, url: str) -> str:
        cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                cache_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
                follow_redirects=True,
                timeout=30.0
            )

            if response.status_code != 200:
                raise Exception(f"Google Cache returned {response.status_code}")

            # Parse and extract original HTML from cache page
            html = self._extract_cached_html(response.text)
            return html

    def _extract_cached_html(self, cache_page: str) -> str:
        """Extract original HTML from Google Cache wrapper."""
        # Google Cache wraps content - need to extract
        # This is simplified, real implementation needs proper parsing
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(cache_page, 'html.parser')

        # Remove Google's wrapper elements
        for elem in soup.select('div[style*="GOOGLE"]'):
            elem.decompose()

        return str(soup)
```

### Direct Googlebot Fetcher

```python
from playwright.async_api import async_playwright

class DirectGooglebotFetcher:
    """Fetches HTML using Googlebot User-Agent."""

    GOOGLEBOT_UA = (
        "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 "
        "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    )

    async def fetch(self, url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self.GOOGLEBOT_UA,
                viewport={'width': 412, 'height': 732}  # Mobile
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                html = await page.content()
                return html
            finally:
                await browser.close()
```

### Wayback Machine Fetcher

```python
import httpx

class WaybackFetcher:
    """Fetches HTML from Internet Archive Wayback Machine."""

    async def fetch(self, url: str) -> str:
        # Get latest snapshot URL
        api_url = f"https://archive.org/wayback/available?url={url}"

        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, timeout=30.0)
            data = response.json()

            snapshots = data.get("archived_snapshots", {})
            closest = snapshots.get("closest", {})

            if not closest.get("available"):
                raise Exception("No Wayback snapshot available")

            snapshot_url = closest["url"]

            # Fetch the snapshot
            html_response = await client.get(snapshot_url, timeout=30.0)
            return html_response.text
```

---

## Мониторинг и адаптация

### Health Dashboard

```python
class HealthMonitor:
    """Monitors source health and sends alerts."""

    def __init__(self, source_manager: SourceManager):
        self.manager = source_manager

    async def get_status(self) -> dict:
        return {
            source.value: {
                "healthy": health.healthy,
                "failures": health.consecutive_failures,
                "last_check": health.last_check
            }
            for source, health in self.manager.health.items()
        }

    async def run_health_checks(self):
        """Periodic health checks for all sources."""
        test_url = "https://example.com"

        for source in self.manager.sources:
            try:
                result = await self.manager.fetchers[source](test_url)
                if result and "Example Domain" in result:
                    self.manager._mark_success(source)
                else:
                    self.manager._mark_failure(source)
            except Exception:
                self.manager._mark_failure(source)
```

### Автоматическая адаптация к изменениям UI

```python
class UIChangeDetector:
    """Detects changes in Google's UI that might break scraping."""

    KNOWN_SELECTORS = {
        "rich_results_button": [
            'text="Посмотреть проверенную страницу"',
            'text="View tested page"',
            'button[data-action="view-html"]',
            '.view-html-button',
        ],
        "html_panel": [
            '.html-content',
            '.rendered-html',
            '[data-panel="html"]',
        ]
    }

    async def find_working_selector(self, page, selector_key: str) -> str:
        """Try multiple selectors and return the one that works."""
        for selector in self.KNOWN_SELECTORS.get(selector_key, []):
            try:
                element = await page.wait_for_selector(selector, timeout=2000)
                if element:
                    return selector
            except:
                continue
        raise Exception(f"No working selector found for {selector_key}")
```

---

## Стратегия кэширования

```python
from datetime import timedelta

class CacheStrategy:
    """Multi-tier caching strategy."""

    # Cache TTLs by source
    TTL = {
        SourceType.RICH_RESULTS: timedelta(hours=24),
        SourceType.GOOGLE_CACHE: timedelta(hours=12),
        SourceType.DIRECT_GOOGLEBOT: timedelta(hours=6),
        SourceType.WAYBACK: timedelta(days=7),
    }

    def __init__(self, redis_client):
        self.redis = redis_client

    async def get(self, url: str) -> Optional[SourceResult]:
        """Get cached result."""
        key = f"seo:html:{url}"
        data = await self.redis.get(key)
        if data:
            return SourceResult.from_json(data)
        return None

    async def set(self, url: str, result: SourceResult):
        """Cache result with source-specific TTL."""
        key = f"seo:html:{url}"
        ttl = self.TTL.get(result.source, timedelta(hours=1))
        await self.redis.setex(key, ttl, result.to_json())
```

---

## Конфигурация через ENV

```python
# config.py
from pydantic_settings import BaseSettings

class SourceConfig(BaseSettings):
    # Enable/disable sources
    ENABLE_RICH_RESULTS: bool = True
    ENABLE_GOOGLE_CACHE: bool = True
    ENABLE_DIRECT_GOOGLEBOT: bool = True
    ENABLE_WAYBACK: bool = True

    # Timeouts
    RICH_RESULTS_TIMEOUT: int = 30000
    GOOGLE_CACHE_TIMEOUT: int = 10000
    DIRECT_TIMEOUT: int = 15000

    # Rate limiting
    RICH_RESULTS_RPM: int = 10  # Requests per minute
    GOOGLE_CACHE_RPM: int = 30

    # Health check
    HEALTH_CHECK_INTERVAL: int = 300  # seconds
    MAX_CONSECUTIVE_FAILURES: int = 3

    class Config:
        env_prefix = "SEO_"
```

---

## Резюме

**Для 100% надёжности:**

1. **4 независимых источника** с автоматическим fallback
2. **Health monitoring** — автоматически отключает сломанные источники
3. **UI Change Detector** — адаптируется к изменениям Google
4. **Multi-tier caching** — снижает нагрузку на источники
5. **Конфигурация через ENV** — можно быстро включить/выключить источник

**Если сломается:**
- Rich Results Test → переключится на Google Cache
- Google Cache → переключится на Direct Googlebot
- Direct Googlebot → переключится на Wayback
- Все 4 → вернёт ошибку и отправит alert
