# SEO-Pocket — Технический анализ

## Результаты исследования affiliate.fm

### Архитектура affiliate.fm

**Frontend (Open Source):**
- Stack: Astro + Preact + TypeScript
- Репозиторий: https://github.com/affiliatefm/affiliate.fm
- Компонент: `GooglebotViewer.tsx` (1113 строк)

**Backend (Closed Source):**
- API: `https://api.affiliate.fm`
- Аутентификация: JWT через Telegram (localStorage key: `tg_auth`)

### API Endpoints affiliate.fm

| Endpoint | Назначение | Параметры |
|----------|------------|-----------|
| `/googlebot-view` | HTML как видит Googlebot | `url`, `chain=1`, `lang`, `mode=user` |
| `/canonical` | Canonical выбранный Google | `url`, `lang` |
| `/google-cache` | Данные из Google Cache | `url`, `lang`, `internal=1` |

### Ключевые интерфейсы данных

```typescript
interface ViewState {
  loading: boolean;
  error: string | null;
  iframeUrl: string | null;
  htmlContent: string | null;           // HTML от Googlebot
  userHtmlContent: string | null;       // HTML от обычного юзера
  userHtmlSource: 'client' | 'api' | 'none';
  chainData: ChainResponse | null;      // Redirect chain
  canonicalData: CanonicalData | null;  // Canonical info
  htmlLang: string | null;
  hreflang: HreflangEntry[];
}

interface CanonicalData {
  url: string;
  googleCanonical: string;
  domain: string;
  canonicalDifferentDomain?: boolean;
  indexingStatus?: {
    potentiallyNotIndexed: boolean;
  };
}

interface ChainResponse {
  success: boolean;
  url: string;
  startDomain: string;
  finalDomain: string;
  redirectCount: number;
  chain: RedirectChainEntry[];
}
```

### Cloaking Detection

affiliate.fm сравнивает два HTML:
1. `htmlContent` — HTML полученный как Googlebot
2. `userHtmlContent` — HTML полученный как обычный пользователь

Алгоритм:
1. Нормализация обоих HTML
2. Извлечение тегов из каждой версии
3. Поиск тегов которые есть только в Googlebot версии
4. Если найдены различия → CLOAKING DETECTED

---

## Возможные подходы к реализации

### Подход 1: Google Search Console API (НЕ ПОДХОДИТ)

**Проблема:** GSC API не предоставляет rendered HTML. Доступны только:
- Данные о производительности (клики, показы)
- Статус индексации
- Sitemaps

**Вывод:** Не подходит для нашей задачи.

### Подход 2: Puppeteer/Playwright с Googlebot User-Agent

**Идея:** Эмулировать Googlebot через headless browser.

**User-Agent:**
```
Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/W.X.Y.Z Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)
```

**Реализация:**
```python
from playwright.async_api import async_playwright

async def fetch_as_googlebot(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        )
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle")
        html = await page.content()
        await browser.close()
        return html
```

**Плюсы:**
- Простая реализация
- Полный контроль

**Минусы:**
- Сайты могут проверять IP (Google IP ranges: 66.249.x.x, 64.233.x.x)
- Rate limiting
- Некоторые сайты требуют авторизацию Google

**Вывод:** Подходит для базового MVP, но не даст 100% точный результат cloaking detection.

### Подход 3: Google Cache Scraping

**URL формат:**
```
https://webcache.googleusercontent.com/search?q=cache:{URL}
```

**Пример:**
```
https://webcache.googleusercontent.com/search?q=cache:https://example.com
```

**Реализация:**
```python
import httpx

async def fetch_google_cache(url: str) -> str:
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
    async with httpx.AsyncClient() as client:
        response = await client.get(cache_url)
        return response.text
```

**Плюсы:**
- Это реальный HTML который видел Googlebot
- Официальный источник Google

**Минусы:**
- Не все страницы закэшированы
- Страницы с `noarchive` не доступны
- Cache может быть устаревшим
- Rate limiting от Google

**Вывод:** Хороший дополнительный источник данных.

### Подход 4: Google Rich Results Test (Исследовать)

**URL:** https://search.google.com/test/rich-results

**Статус:** Google НЕ предоставляет официальный API.

**Возможность:** Scraping через Playwright (reverse engineering).

**Риски:**
- Нестабильно
- Может сломаться в любой момент
- Возможны блокировки

**Вывод:** Можно исследовать как "лазейку", но не надежно.

### Подход 5: Прокси через Google IP ranges

**Идея:** Арендовать прокси с IP адресами из диапазонов Google.

**Google IP ranges:**
- 66.249.64.0/19 (Googlebot)
- 64.233.160.0/19
- 72.14.192.0/18

**Проблема:** Легальные прокси с Google IP практически недоступны.

**Вывод:** Теоретически возможно, практически сложно.

---

## Рекомендуемая архитектура MVP

### Гибридный подход

Комбинация нескольких методов для максимальной точности:

```
┌────────────────────────────────────────────────────────┐
│                    SEO-Pocket MVP                       │
├────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────┐    ┌─────────────────┐            │
│  │   User Input    │    │   URL Analyzer  │            │
│  │   (URL field)   │───▶│   (normalize)   │            │
│  └─────────────────┘    └────────┬────────┘            │
│                                  │                      │
│         ┌────────────────────────┼────────────────┐    │
│         │                        │                │    │
│         ▼                        ▼                ▼    │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐│
│  │  Playwright  │   │ Google Cache │   │  Direct HTTP ││
│  │  (Googlebot  │   │  Scraper     │   │  (User view) ││
│  │   UA)        │   │              │   │              ││
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘│
│         │                  │                  │        │
│         └────────────┬─────┴──────────────────┘        │
│                      │                                  │
│                      ▼                                  │
│           ┌─────────────────────┐                      │
│           │   HTML Parser       │                      │
│           │   - Title, H1       │                      │
│           │   - Meta tags       │                      │
│           │   - Canonical       │                      │
│           │   - Hreflang        │                      │
│           │   - Status codes    │                      │
│           └──────────┬──────────┘                      │
│                      │                                  │
│                      ▼                                  │
│           ┌─────────────────────┐                      │
│           │  Cloaking Detector  │                      │
│           │  (Compare bot vs    │                      │
│           │   user HTML)        │                      │
│           └──────────┬──────────┘                      │
│                      │                                  │
│                      ▼                                  │
│           ┌─────────────────────┐                      │
│           │   Response Builder  │                      │
│           │   (JSON + HTML)     │                      │
│           └─────────────────────┘                      │
│                                                         │
└────────────────────────────────────────────────────────┘
```

### Tech Stack

```
Backend:
- FastAPI (Python 3.11+)
- Playwright (async browser automation)
- BeautifulSoup4 / lxml (HTML parsing)
- httpx (async HTTP client)
- Redis (caching)
- PostgreSQL (history storage)

Frontend:
- Next.js 14 или Astro
- TypeScript
- Tailwind CSS
- shadcn/ui
```

### API Endpoints (MVP)

```
POST /api/analyze
  Body: { "url": "https://example.com" }
  Response: {
    "url": "https://example.com",
    "title": "...",
    "h1": "...",
    "description": "...",
    "canonical": "...",
    "hreflang": [...],
    "statusCode": 200,
    "redirectChain": [...],
    "googlebotHtml": "...",
    "userHtml": "...",
    "cloakingDetected": false,
    "cloakingDiffs": []
  }

GET /api/cache/{url}
  Response: Google Cache HTML

GET /api/history/{domain}
  Response: Historical analysis data
```

---

## План реализации

### Фаза 1: MVP (до конца января)

1. **Backend API**
   - [ ] Playwright setup для Googlebot emulation
   - [ ] HTML parser (BeautifulSoup)
   - [ ] Cloaking detection algorithm
   - [ ] Basic API endpoints

2. **Frontend**
   - [ ] URL input form
   - [ ] Results display (tabs: Overview, Source, Cloaking)
   - [ ] Basic styling

### Фаза 2: Google Cache Integration

- [ ] Google Cache scraper
- [ ] Cache comparison with live version
- [ ] Historical tracking

### Фаза 3: Advanced Features

- [ ] Redirect chain visualization
- [ ] Hreflang analysis
- [ ] Batch URL checking
- [ ] Export reports

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Rate limiting Google | Высокая | Прокси ротация, delays |
| Неточный cloaking detection | Средняя | Несколько методов проверки |
| Блокировка IP | Средняя | Residential прокси |
| Google Cache недоступен | Низкая | Fallback на Playwright |

---

## Следующие шаги

1. Создать базовую структуру проекта
2. Реализовать Playwright fetcher с Googlebot UA
3. Реализовать HTML parser
4. Создать API endpoint
5. Базовый UI
6. Тестирование на реальных сайтах
