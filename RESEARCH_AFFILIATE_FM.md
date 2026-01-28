# Reverse Engineering affiliate.fm - Разведданные

## Дата исследования: 2026-01-28

---

## 1. API Endpoints affiliate.fm

### Googlebot View
```
POST https://affiliate.fm/api/googlebot-view
Body: { url: "https://example.com" }
Response: HTML контент как видит Googlebot
```

### Google Canonical
```
POST https://affiliate.fm/api/canonical
Body: { url: "https://example.com" }
Response: {
  canonical: "https://...",  // Google canonical URL
  firstIndexed: "2023-12-07",
  lastIndexed: "2025-12-19",
  relatedDomains: [...]
}
```

### Google Cache
```
POST https://affiliate.fm/api/google-cache
Body: { url: "https://example.com" }
```

---

## 2. Технологии affiliate.fm

### Frontend
- **Astro 5** + Preact (НЕ SvelteKit как думали раньше!)
- TypeScript, Tailwind CSS
- Деплой: GitHub Pages через Astro CI/CD
- Файлы: `GooglebotViewer.tsx`, `ContentRewriter.tsx`

### Backend
- Хостинг: **AWS API Gateway** (api.affiliate.fm)
- Backend код **закрытый** — не в публичном репо
- Перезапуск сервера каждый час (возможно для сброса ban-листа IP)

### 🔑 КЛЮЧЕВОЕ ОТКРЫТИЕ: Zyte API
- Используют **Zyte API** (бывший Scrapy Cloud) для bypass Cloudflare
- Это **коммерческий легальный сервис** для web scraping
- Endpoint: `https://api.zyte.com/v1/extract`
- Zyte имеет свою инфраструктуру residential proxies и headless browsers

---

## 3. Как получают контент — РАЗГАДКА!

### ✅ ПОДТВЕРЖДЕНО: Zyte API
```javascript
// ContentRewriter.tsx lines 183-200
const res = await fetch("https://api.zyte.com/v1/extract", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Basic ${btoa(apiKey + ":")}`,  // Base64 encoded API key
  },
  body: JSON.stringify({
    url,
    article: true,
    browserHtml: true  // ← Рендерит в headless browser!
  }),
});
```

### Что такое Zyte?
- **Коммерческий сервис** (бывший Scrapy Cloud) — https://zyte.com
- Специализируется на обходе anti-bot защиты (Cloudflare, Datadome, etc.)
- Имеет инфраструктуру residential proxies + headless browsers
- `browserHtml: true` = полный рендеринг JavaScript
- **Это НЕ Google Translate proxy!**

### Их архитектура:
1. **Для подписчиков**: `/zyte-parse` — их backend проксирует к Zyte API
2. **Для пользователей с ключом**: Прямой вызов `api.zyte.com` из браузера
3. **Кэширование**: `x-cache: HIT` — закэшированные результаты бесплатны

### Цена Zyte API:
- $0.001 - $0.003 per request (зависит от сложности)
- Есть бесплатный trial
- https://zyte.com/pricing

### Наш Zyte API Key:
```
258a344fed8647e990ac02a92fd7105b
```

### Google Translate Proxy (устаревшая гипотеза)
```
https://translate.google.com/website?sl=auto&tl=en&u=TARGET_URL
```
- МЫ используем Google Translate как прокси
- Cloudflare-protected сайты возвращают challenge page
- affiliate.fm НЕ использует Google Translate для casino сайтов — они используют Zyte!

---

## 4. Как получают Google Canonical

### Метод 1: info: оператор (DataForSEO)
```
info:https://example.com
```
- Возвращает индексированную версию URL
- НЕ работает для многих casino сайтов

### Метод 2: site: оператор (fallback)
```
site:base-domain.com
```
- Возвращает первый результат для домена

### Метод 3: ??? (affiliate.fm знает что-то ещё)
- Для `paying-casinos-ca.it.com` они показывают `www.recoveryforall.ca` как Google Canonical
- Это ДРУГОЙ домен! Значит они используют что-то кроме info:/site:
- Возможно: `related:` оператор или Google Search Console API

---

## 5. Как получают даты

### Wayback Machine CDX API
```
https://web.archive.org/cdx/search/cdx?url=URL&limit=1&output=json&fl=timestamp
```
- first_archived: первый snapshot
- last_archived: последний snapshot (sort=reverse)

### DataForSEO (alternative)
- Может возвращать даты из Google index

---

## 6. Сравнение результатов

### casino-ohne.gaststaette-hillenbrand.de

| Метрика | affiliate.fm | SEO Pocket |
|---------|-------------|------------|
| Контент | "2026" (свежий) | 403 Forbidden |
| Google Canonical | gaststaette-hillenbrand.de | gaststaette-hillenbrand.de ✓ |
| First Indexed | 2023-12-07 | null |
| Last Indexed | 2025-12-19 | null |
| HTML Lang | de | null (403) |
| Hreflang | x-default, de, ch | null (403) |

### paying-casinos-ca.it.com

| Метрика | affiliate.fm | SEO Pocket |
|---------|-------------|------------|
| Контент | "BEST PAYING" (свежий) | 403 Forbidden |
| Google Canonical | www.recoveryforall.ca (!!) | null |
| First Indexed | 2005-05-27 | null |
| Last Indexed | 2026-01-20 | null |

---

## 7. Ключевые проблемы SEO Pocket

1. **Cloudflare Challenge** — Google Translate возвращает challenge page для casino сайтов
2. **Google Canonical для it.com** — не находит (recoveryforall.ca — другой домен!)
3. **Wayback даты не показываются** — возможно не вызывается или не отображается

---

## 8. ✅ РАЗГАДКА: Как affiliate.fm обходит Cloudflare

### ОТВЕТ: Zyte API (коммерческий сервис)

Они НЕ изобретают велосипед. Они платят за Zyte API который:
1. Имеет pool residential proxies
2. Имеет headless browsers с anti-detection
3. Автоматически решает Cloudflare challenges
4. Ротирует IP адреса

### Код из их репозитория (доказательство):
```javascript
// src/templates/_affiliatefm/components/tools/ContentRewriter.tsx
async function parseUrlDirect(url: string, apiKey: string) {
  const res = await fetch("https://api.zyte.com/v1/extract", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Basic ${btoa(apiKey + ":")}`,
    },
    body: JSON.stringify({ url, article: true, browserHtml: true }),
  });
  // ...
}
```

### Почему наши гипотезы были неверны:
- ❌ FlareSolverr — они НЕ используют open-source решение
- ❌ Google Translate — возвращает Cloudflare challenge для casino
- ❌ Самодельные прокси — слишком сложно и ненадёжно
- ✅ Zyte API — платный сервис который всё это делает

---

## 9. TODO: Что делать нам

### Вариант 1: Zyte API (как affiliate.fm)
- ✅ Работает гарантированно
- ❌ Платный ($0.001-$0.003 per request)
- Регистрация: https://zyte.com/sign-up

### Вариант 2: FlareSolverr (бесплатно)
- ✅ Open-source, self-hosted
- ❌ Требует Docker, медленнее
- ❌ Менее надёжный чем Zyte
- Мы УЖЕ имеем код в fetcher.py!

### Вариант 3: ScrapingBee / ScraperAPI (альтернативы Zyte)
- Другие коммерческие сервисы
- Сравнить цены и качество

### Нерешённые вопросы:
- [ ] Понять откуда берут Google Canonical для cross-domain (it.com → recoveryforall.ca)
- [ ] Проверить related: оператор в Google

### Проверено через браузер (2026-01-28):
**paying-casinos-ca.it.com:**
- Google Canonical: `www.recoveryforall.ca` (CROSS-DOMAIN!)
- HTML Canonical: `www.recoveryforall.ca`
- Даты: 2005-05-27 → 2026-01-20
- HTML Lang: en-CA
- Контент: "BEST PAYING ONLINE" (свежий!)

**Вывод:** Они определяют cross-domain canonical. Возможно через:
1. Google's `related:` оператор
2. Прямой fetch страницы и парсинг `<link rel="canonical">`
3. Какой-то другой API

---

## 10. Файлы affiliate.fm для анализа

- `/tools/googlebot-view/` - Googlebot viewer
- `/tools/google-cache/` - Google Cache viewer
- `/api/googlebot-view` - API endpoint
- `/api/canonical` - Canonical API
- `GooglebotViewer.DUiEXFIM.js` - Frontend component

---

## 11. Дополнительные находки (2026-01-28)

### Frontend анализ:
- Frontend **НЕ содержит** Google Translate proxy
- Все запросы идут через закрытый backend `api.affiliate.fm`
- Endpoints: `/googlebot-view`, `/google-cache`, `/canonical`, `/zyte-parse`

### Кэширование:
- `x-cache: HIT` — закэшированные результаты бесплатны
- Для новых URL нужна подписка Telegram (401 Unauthorized)
- Время ответа из кэша: ~1.5 сек

### Backend (закрытый):
- Хостинг: AWS API Gateway
- Для `/zyte-parse` — точно проксирует к Zyte API
- Для `/googlebot-view` — неизвестно (но скорее всего тоже Zyte или аналог)

---

## 12. 🚨 ГЛАВНОЕ ОТКРЫТИЕ (2026-01-28 вечер)

### Проблема с Zyte API

Zyte API **обходит Cloudflare**, но сайты всё равно возвращают **обычный контент (2025)**, а не **cloaked контент (2026)**.

**Почему?**
- Zyte использует residential proxies, не Google IPs
- Сайты определяют что это не Googlebot → показывают user version
- affiliate.fm показывает **2026** = они получают cloaked content

### Ключевое доказательство

Из маркетинга affiliate.fm (`googlebot-view.mdx`):
```
"Fetches pages from Google's actual IP ranges"
"View pages from Google's IP ranges"
"Fetches from legitimate Google IP ranges"
```

### Тесты подтверждают:

| Source | Casino URL | Контент | Вывод |
|--------|-----------|---------|-------|
| Zyte API | casino-ohne... | **2025** год | Обычная страница |
| affiliate.fm | casino-ohne... | **2026** год | Cloaked content |
| Google Rich Results Test | casino-ohne... | **2026** год | Real Googlebot |

### Вывод

affiliate.fm использует **НЕ Zyte** для Googlebot View!

Zyte используется ТОЛЬКО для Content Rewriter (парсинг статей).
Для Googlebot View они используют что-то с Google IP адресами.

### Гипотезы как они это делают:

1. **Google Cloud Functions** — запросы с GCP идут с Google IP ranges
2. **DataForSEO API** — имеют crawler инфраструктуру
3. **Puppeteer + Google Cloud Run** — тот же эффект (Google IPs)
4. **Rich Results Test парсинг** — автоматизация браузера
5. **Приватный Google API** — маловероятно

### Скорость ответа (доказательство)

- `/googlebot-view` за **100-230ms** — слишком быстро для парсинга Rich Results Test
- Если бы парсили RRT через Puppeteer — было бы 5-15 секунд
- Скорее всего **кэширование** + **GCP/DataForSEO**

---

## 13. Следующие шаги исследования

### Проверить гипотезу GCP:

1. Развернуть Cloud Function на GCP
2. Сделать запрос к casino сайту
3. Проверить получаем ли cloaked content

### Проверить DataForSEO:

- У них есть SERP API с real Google data
- Возможно есть и crawler API

### Альтернативный путь:

1. **Strategy 0**: Rich Results Test (ручной парсинг) — для cloaked detection
2. **Strategy 1**: Zyte — для Cloudflare bypass + regular content
3. **Strategy 2**: Google Translate — бесплатный fallback

---

## 14. Техническая архитектура affiliate.fm (обновлённая)

```
┌─────────────────┐     ┌─────────────────┐
│  Frontend       │     │  api.affiliate  │
│  (Astro+Preact) │ ──→ │  (AWS API GW)   │
└─────────────────┘     └────────┬────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  /zyte-parse    │   │ /googlebot-view │   │  /canonical     │
│  (Zyte API)     │   │  (GCP? DFSEO?)  │   │  (DataForSEO?)  │
│                 │   │                 │   │                 │
│ Content Rewriter│   │ CLOAKED content │   │ Google index    │
│ Article parsing │   │ Google IPs      │   │ info: operator  │
└─────────────────┘   └─────────────────┘   └─────────────────┘
```

### Различие между tools:

| Tool | API | Метод | Результат |
|------|-----|-------|-----------|
| Content Rewriter | Zyte | Residential proxy | User content |
| Googlebot View | ??? | Google IPs | Bot content |
| Google Cache | ??? | Cache API | Cached content |
| Canonical | DataForSEO? | info: search | Google canonical |

---

## 15. Исследование Google IP решений

### Google IP диапазоны (официальные JSON):

| Источник | Диапазоны IPv4 | Reverse DNS |
|----------|---------------|-------------|
| Googlebot | `192.178.4-7.x`, `34.x.x.x` | *.googlebot.com |
| User-triggered | `142.250.32-33.x`, `192.178.10-13.x` | *.gae.googleusercontent.com |
| Cloud Run/Functions | Динамические из пула | ? |

### DataForSEO On-Page API:
- ✅ Позволяет custom user-agent
- ❌ Использует СВОИ IP адреса (не Google)
- Не подходит для cloaking detection

### Google Cloud approach:

Cloud Run/Functions по умолчанию используют динамические IP из пула Google.

**Открытые вопросы:**
1. Какой именно диапазон IP у Cloud Run?
2. Резолвится ли reverse DNS в google.com?
3. Проверяют ли casino сайты только IP или и rDNS?

**Тест для проверки:**
```python
# Развернуть на Cloud Run и проверить
import requests
r = requests.get('https://httpbin.org/ip')
print(r.json())  # Какой IP?

# Затем проверить cloaking
r2 = requests.get('https://casino-ohne.gaststaette-hillenbrand.de/',
    headers={'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'})
print('2026' in r2.text)  # Cloaked?
```

---

## 16. Финальные выводы

### Что мы ТОЧНО знаем:

1. **affiliate.fm для Googlebot View использует Google IPs** (из маркетинга)
2. **Zyte API НЕ даёт cloaked content** — только обход Cloudflare
3. **Rich Results Test работает** — показывает cloaked content (2026)
4. **Скорость 100-230ms** — слишком быстро для парсинга RRT

### Наиболее вероятная гипотеза:

affiliate.fm использует **Google Cloud** (Run/Functions) с:
1. Googlebot User-Agent
2. IP из диапазона Google
3. Агрессивное кэширование результатов

Либо у них есть **приватное партнёрство** с Google/DataForSEO.

### Рекомендуемый план для SEO Pocket:

**Strategy 0: Google Cloud Proxy (для cloaked content)**
- Cloud Run функция с Googlebot UA
- Нужно протестировать работает ли

**Strategy 1: Zyte API (для Cloudflare bypass)**
- УЖЕ интегрирован и работает
- Даёт обычный контент (не cloaked)

**Strategy 2: Google Translate (бесплатный fallback)**
- Работает для простых сайтов
- Не работает для Cloudflare

---

## 17. Попытка автоматизации Rich Results Test (2026-01-28)

### Проблема

При попытке автоматизировать Rich Results Test через Playwright обнаружено:

**"Something went wrong - Log in and try again"**

Rich Results Test **требует авторизацию в Google аккаунт**!

### Скриншот ошибки

Headless browser без авторизации получает ошибку вместо результатов.

### Возможные решения

1. **Сохранить cookies** из залогиненного браузера
2. **OAuth авторизация** через Google API
3. **Ручной режим** — пользователь копирует HTML из RRT

### Как affiliate.fm это решает?

Вероятные варианты:
1. **Кэширование** — запускают RRT по расписанию, кэшируют результаты
2. **Авторизованные сессии** — сохранённые cookies Google аккаунта
3. **Google Cloud** — запросы с GCP IP + Googlebot UA (без RRT)
4. **Партнёрство с Google/DataForSEO** — приватный API

### Скорость affiliate.fm (100-230ms)

Слишком быстро для real-time RRT парсинга (5-15 сек).
Это подтверждает что они используют **кэширование**.

### Вывод для SEO Pocket

На данный момент:
- **Google Translate** — для сайтов без Cloudflare (Google IP, бесплатно)
- **Zyte** — для Cloudflare bypass (user content)
- **Cloaking detection** — сравнение Google Translate vs Zyte

TODO в будущем:
- [ ] Решить проблему авторизации для Rich Results Test
- [ ] Или найти альтернативный источник Googlebot view
- [ ] Рассмотреть Google Cloud approach

---

## 18. Текущая архитектура SEO Pocket

```
                    ┌─────────────────┐
                    │   User Request  │
                    └────────┬────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────┐
│                    SmartFetcher                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Strategy 0: Google Translate                              │
│  ├── Google IP → может получить cloaked content           │
│  ├── Бесплатно, быстро                                     │
│  └── НО: Cloudflare блокирует для casino сайтов            │
│                                                            │
│  Strategy 1: Rich Results Test (DISABLED - needs auth)     │
│  ├── Real Googlebot view!                                  │
│  └── Требует Google авторизацию                            │
│                                                            │
│  Strategy 2: Zyte API                                      │
│  ├── Обходит Cloudflare                                    │
│  ├── Residential proxies                                   │
│  └── Возвращает USER content (не cloaked!)                 │
│                                                            │
│  Strategy 3-6: Direct UA, Stealth, FlareSolverr, Proxy     │
│                                                            │
└────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────┐
│                  Cloaking Detection                        │
├────────────────────────────────────────────────────────────┤
│  Сравнивает bot_html vs user_html                          │
│  Если разница в SEO элементах → CLOAKING DETECTED          │
└────────────────────────────────────────────────────────────┘
```

### Ограничения текущей версии

1. **Для Cloudflare сайтов** — не можем получить реальный Googlebot view
2. **Zyte даёт user content** — не cloaked
3. **Google Translate блокируется** — Cloudflare детектит

### Что работает

1. **Простые сайты** — Google Translate показывает как Googlebot видит
2. **Cloudflare сайты** — Zyte обходит защиту, получаем хоть что-то
3. **SEO метаданные** — title, h1, description, canonical, hreflang
4. **Google Canonical** — через DataForSEO

---

## 19. 🚨 ГЛАВНОЕ ОТКРЫТИЕ: Google App Engine Proxy (2026-01-28)

### Тест icanhazip.com через affiliate.fm

При запросе `https://icanhazip.com` через affiliate.fm Googlebot View получили:

**IP: `66.249.93.41`**

### Проверка IP

```bash
$ host 66.249.93.41
41.93.249.66.in-addr.arpa domain name pointer google-proxy-66-249-93-41.google.com.

$ whois 66.249.93.41
NetRange:       66.249.64.0 - 66.249.95.255
NetName:        GOOGLE
```

### Вывод

**affiliate.fm использует Google App Engine** для Googlebot View:

1. Backend развёрнут на **Google App Engine**
2. Когда App Engine делает HTTP запрос через URLFetch API
3. Запрос идёт с IP из диапазона `66.249.x.x`
4. Reverse DNS: `google-proxy-*.google.com`
5. Сайты видят Google IP → отдают **cloaked content**!

### Почему это работает

Cloaking сайты проверяют:
1. ✅ IP из диапазона Google (`66.249.x.x`) — App Engine даёт это!
2. ✅ Reverse DNS резолвится в `*.google.com` — App Engine даёт это!
3. ✅ User-Agent = Googlebot — можно установить любой

### Диапазоны Google App Engine

Outbound IP адреса App Engine:
- `66.249.64.0 - 66.249.95.255` (основной диапазон)
- Reverse DNS: `google-proxy-*.google.com`
- Динамические, меняются, но всегда Google-owned

### Как реализовать для SEO-Pocket

**Google Cloud Function:**

```python
import functions_framework
import requests

@functions_framework.http
def fetch_as_googlebot(request):
    url = request.args.get('url')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    
    return {
        'html': response.text,
        'status': response.status_code,
        'headers': dict(response.headers)
    }
```

**App Engine (более надёжно для Google IP):**

```yaml
# app.yaml
runtime: python311
instance_class: F1

handlers:
- url: /.*
  script: auto
```

### Тарификация

- **Cloud Functions**: 2M бесплатных вызовов/месяц
- **App Engine**: 28 instance-hours/день бесплатно
- После free tier: ~$0.0000025 за вызов

### Источники

- https://cloud.google.com/appengine/docs/standard/outbound-ip-addresses
- https://developers.google.com/search/blog/2014/03/app-engine-ip-range-change-notice

---

## 20. Полная архитектура affiliate.fm (финальная)

```
┌─────────────────────────────────────────────────────────────────┐
│                      affiliate.fm                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Frontend (Astro + Preact)          API (AWS API Gateway)        │
│  ├── GooglebotViewer.tsx            ├── /telegram-auth           │
│  ├── GoogleCacheViewer.tsx          ├── /googlebot-view ──────┐  │
│  ├── ContentRewriter.tsx            ├── /canonical             │  │
│  └── TelegramAuth.tsx               ├── /google-cache          │  │
│                                     └── /zyte-parse            │  │
│                                                                 │  │
└─────────────────────────────────────────────────────────────────┘
                                                                  │
                        ┌─────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────┐
        │     Google App Engine / Lambda     │
        │                                    │
        │  requests.get(url, headers={       │
        │    'User-Agent': 'Googlebot/2.1'   │
        │  })                                │
        │                                    │
        │  Outbound IP: 66.249.93.x          │
        │  Reverse DNS: google-proxy-*.com   │
        └───────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────┐
        │         Target Website             │
        │                                    │
        │  Checks:                           │
        │  ✓ IP in Google range (66.249.x)   │
        │  ✓ rDNS = *.google.com            │
        │  ✓ User-Agent = Googlebot         │
        │                                    │
        │  → Returns CLOAKED content (2026)  │
        └───────────────────────────────────┘
```

### Итоговое сравнение методов

| Метод | IP Range | rDNS | Cloaked Content? | Скорость |
|-------|----------|------|------------------|----------|
| Zyte API | Residential | нет | ❌ НЕТ (2025) | Быстро |
| Google Translate | 142.250.x | *.google.com | ⚠️ Cloudflare блок | Быстро |
| Rich Results Test | 66.249.x | *.googlebot.com | ✅ ДА (2026) | Медленно |
| **App Engine** | 66.249.x | google-proxy-*.com | ✅ ДА (2026) | **Быстро** |

### Вывод

**App Engine/Cloud Functions** — это решение affiliate.fm:
- Быстро (100-230ms как у них)
- Google IP автоматически
- Масштабируется
- Дёшево (почти бесплатно)


---

## 21. Детальное исследование Google IP (продолжение)

### Тест 1: icanhazip.com через affiliate.fm
- **IP:** `66.249.93.41`
- **rDNS:** `google-proxy-66-249-93-41.google.com`
- **Категория:** google_proxy

### Тест 2: ifconfig.me/ip через affiliate.fm
- **IP:** `142.250.32.40`
- **rDNS:** `google-proxy-142-250-32-40.google.com`
- **Категория:** google_proxy

### Тест 3: Наш App Engine
- **IP:** `34.96.45.199`
- **rDNS:** `199.45.96.34.bc.googleusercontent.com`
- **Категория:** cloud (Cloudflare блокирует!)

### Тест 4: Наш Cloud Function
- **IP:** `34.96.63.82`
- **rDNS:** `82.63.96.34.bc.googleusercontent.com`
- **Категория:** cloud (Cloudflare блокирует!)

### Вывод

affiliate.fm получает IP из диапазонов:
- `66.249.x.x` → rDNS: `google-proxy-*.google.com`
- `142.250.x.x` → rDNS: `google-proxy-*.google.com`

Эти IP **НЕ** в официальных Googlebot ranges, но:
1. Принадлежат Google (whois подтверждает)
2. rDNS резолвится в `*.google.com`
3. Сайты доверяют им как Google-сервисам

### Какой сервис даёт такие IP?

Гипотезы:
1. **Google Apps Script UrlFetch** — возможно даёт google-proxy IP
2. **Старый App Engine (Python 2.7)** — legacy URLFetch API
3. **Google Sheets IMPORTXML** — делает запросы с Google IP
4. **Google Sites fetch** — внутренний сервис

### Сбор IP диапазонов

Собрано 1529 диапазонов из официальных источников:
- Googlebot: 307 ranges
- Special crawlers: 264 ranges  
- User-triggered: 958 ranges

Файл: `backend/data/google_ips.json`


---

## 22. ПРОРЫВ: Google Sheets использует google-proxy IP! (2026-01-28)

### Тест через Google Sheets IMPORTDATA

Формула: `=IMPORTDATA("https://api.ipify.org")`

**Результат: IP `66.102.8.132`**

```bash
$ host 66.102.8.132
132.8.102.66.in-addr.arpa domain name pointer google-proxy-66-102-8-132.google.com.
```

### ВЫВОД

**Google Sheets IMPORTDATA/IMPORTXML использует `google-proxy-*.google.com` IP!**

Это ТОТ ЖЕ тип IP что у affiliate.fm:
- affiliate.fm: `66.249.93.41` → `google-proxy-66-249-93-41.google.com`
- Google Sheets: `66.102.8.132` → `google-proxy-66-102-8-132.google.com`

### Проблема

IMPORTXML не может установить User-Agent = Googlebot.
Cloudflare блокирует запросы без правильного UA.

### Решение

**Google Apps Script UrlFetchApp** позволяет:
1. Установить любой User-Agent
2. Запросы идут с google-proxy IP

```javascript
function fetchAsGooglebot(url) {
  var options = {
    "method": "get",
    "headers": {
      "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    },
    "muteHttpExceptions": true
  };
  return UrlFetchApp.fetch(url, options).getContentText();
}
```

### Архитектура решения

```
SEO-Pocket Backend
        │
        ▼
Google Apps Script (Web App)
        │
        ├── IP: 66.102.x.x (google-proxy)
        ├── rDNS: google-proxy-*.google.com  
        └── User-Agent: Googlebot/2.1
        │
        ▼
Target Website
        │
        └── Sees Google IP + Googlebot UA
        └── Returns CLOAKED content!
```

### TODO

1. [x] Создать Google Apps Script Web App
2. [ ] Задеплоить как API endpoint
3. [ ] Интегрировать в SEO-Pocket backend
4. [ ] Тестировать на casino сайтах


---

## 23. ДОСТУП К API affiliate.fm ПОЛУЧЕН! (2026-01-28)

### Токен авторизации

Из localStorage браузера (`tg_auth`):

```
Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
User: Alex Nikole (@under_protect)
Expires: 1770129796 (~7 дней)
```

### Работающие endpoints

#### 1. Googlebot View
```bash
curl "https://api.affiliate.fm/googlebot-view?url=URL&lang=en" \
  -H "Authorization: Bearer TOKEN"
```
Возвращает: HTML как видит Googlebot (cloaked content!)

#### 2. Canonical
```bash
curl "https://api.affiliate.fm/canonical?url=URL&lang=en" \
  -H "Authorization: Bearer TOKEN"
```
Возвращает JSON:
```json
{
  "googleCanonical": "https://...",
  "firstIndexed": {"date": "2023-12-07"},
  "published": {"date": "2025-12-19"},
  "relatedDomains": ["..."],
  "domainMerge": {"detected": true}
}
```

#### 3. Google Cache
```bash
curl "https://api.affiliate.fm/google-cache?url=URL&lang=en" \
  -H "Authorization: Bearer TOKEN"
```
Возвращает: HTML из Google Cache с alternate ссылками

### Тест на casino сайте

```bash
curl "https://api.affiliate.fm/googlebot-view?url=https://casino-ohne.gaststaette-hillenbrand.de/" \
  -H "Authorization: Bearer TOKEN"
```

**Результат:** HTML с `<title>Casinos ohne limit OASIS ... 2026</title>`

**ЭТО CLOAKED CONTENT!** 2026 год = контент для Googlebot!

### Выводы

1. affiliate.fm API полностью работает с нашим токеном
2. Токен действует ~7 дней (JWT exp)
3. Можно интегрировать их API в наш backend как один из источников
4. Или reverse-engineer их метод (google-proxy IP)

### Архитектура с affiliate.fm API

```
SEO-Pocket → affiliate.fm API → google-proxy IP → Target site
                ↓
            Cloaked content (2026)
```

Преимущества:
- Работает прямо сейчас
- Бесплатно (пока есть подписка)
- Быстро (100-230ms с их кэшем)

Минусы:
- Зависимость от стороннего сервиса
- Токен истекает
- Могут заблокировать

---

## 24. ИТОГОВОЕ ИССЛЕДОВАНИЕ IP (2026-01-28)

### Сравнение IP типов

| Источник | IP пример | rDNS | Cloudflare | Cloaking |
|----------|-----------|------|------------|----------|
| affiliate.fm | `66.249.93.41` | `google-proxy-*.google.com` | ✅ Пропускает | ✅ Даёт cloaked |
| Google Sheets | `66.102.8.132` | `google-proxy-*.google.com` | ✅ Но нет UA | ❌ Нет UA |
| Наш App Engine | `34.96.45.199` | `*.googleusercontent.com` | ❌ Блокирует | ❌ |
| Наш Cloud Function | `34.96.63.82` | `*.googleusercontent.com` | ❌ Блокирует | ❌ |
| Zyte API | Residential | Разные ISP | ✅ Bypass | ❌ User content |

### Ключевой вопрос: Какой Google сервис даёт `google-proxy-*.google.com` rDNS?

**Проверенные (НЕ работают):**
- ❌ Google App Engine Standard — даёт `*.googleusercontent.com`
- ❌ Google Cloud Functions — даёт `*.googleusercontent.com`
- ❌ Google Cloud Run — даёт `*.googleusercontent.com`

**Потенциальные (нужно тестить):**
- ⏳ Google Apps Script UrlFetchApp — НУЖЕН ТЕСТ
- ⏳ Legacy App Engine (Python 2.7 URLFetch) — deprecated
- ? Google internal service (может быть недоступен публично)

### Гипотеза о affiliate.fm

affiliate.fm возможно использует:
1. **Google Apps Script** как прокси (UrlFetchApp)
2. **Или** какой-то legacy/internal Google сервис
3. **Или** партнёрство с Google/другим провайдером

---

## 25. ПЛАН ДЕЙСТВИЙ

### Вариант A: Google Apps Script (тестируем сейчас)

1. Создать Google Apps Script Web App
2. Функция UrlFetchApp с Googlebot User-Agent
3. Проверить какой IP используется
4. Если google-proxy — интегрировать в SEO-Pocket

### Вариант B: affiliate.fm API (временное решение)

1. Использовать их API с токеном подписчика
2. Минусы: ненадёжно, этически сомнительно
3. Плюс: работает прямо сейчас

### Вариант C: Полный reverse-engineering affiliate.fm

1. Облепить все их endpoints саб-агентами
2. Проанализировать все функции
3. Выцепить все технические детали

---

## 26. TODO: Полный аудит affiliate.fm

### Endpoints для проверки:
- [ ] `/googlebot-view` — основной, нужно понять как работает
- [ ] `/canonical` — откуда берут Google Canonical
- [ ] `/google-cache` — откуда берут cached version
- [ ] `/zyte-parse` — для Content Rewriter
- [ ] `/telegram-auth` — как работает авторизация
- [ ] Другие hidden endpoints?

### Вопросы для исследования:
- [ ] Какой бэкенд используют (AWS Lambda? GCP? свой сервер?)
- [ ] Как получают google-proxy IP?
- [ ] Как кэшируют результаты?
- [ ] Какие rate limits?
- [ ] Как обновляют токены Telegram?

### Исследование фронтенда:
- [ ] Все JS файлы на предмет API calls
- [ ] Network tab при использовании
- [ ] localStorage/sessionStorage данные
- [ ] Cookies

---

## 27. ЖЁСТКИЙ АУДИТ API (2026-01-28) 🔥

### Инфраструктура backend

**Подтверждено из response headers:**
```
x-amzn-requestid: b96483ad-702d-471e-86d8-4dd539a033f5
x-amz-apigw-id: X6SeGG2BliAEM8g=
x-amzn-trace-id: Root=1-697a6459-2bee41024ce4153654f4a6e4
```

**Вывод: AWS API Gateway + AWS Lambda!**

### Все найденные endpoints

| Endpoint | Method | Auth | Описание |
|----------|--------|------|----------|
| `/googlebot-view` | GET | Required | Fetch как Googlebot (google-proxy IP!) |
| `/canonical` | GET | Required | Google canonical + dates |
| `/google-cache` | GET | Required | Google cached version |
| `/zyte-parse` | GET | Required | Zyte API proxy для Content Rewriter |
| `/telegram-auth` | GET | Optional | Проверка Telegram авторизации |

### Детали /googlebot-view

**Request:**
```
GET https://api.affiliate.fm/googlebot-view?url=URL&lang=en
Authorization: Bearer JWT_TOKEN
```

**Response headers:**
```
content-type: text/html; charset=utf-8  (для HTML)
content-type: application/json          (для ошибок)
x-cache: MISS/HIT                       (кэширование)
access-control-allow-origin: *
```

**Response успех:**
```html
<html lang="ru"><head></head><body><pre>66.249.93.37</pre></body></html>
```

**Response ошибка:**
```json
{"success":false,"error":"Site blocks bot traffic","url":"...","cached":true}
```

### Детали /canonical

**Response:**
```json
{
  "url": "https://example.com",
  "googleCanonical": "http://example.com/",
  "domain": "example.com",
  "firstIndexed": {
    "timestamp": 1099555200,
    "date": "2004-11-04T08:00:00.000Z"
  },
  "published": {
    "timestamp": 1768550400,
    "date": "2026-01-16T08:00:00.000Z"
  }
}
```

### Детали /telegram-auth

**Response (не авторизован):**
```json
{
  "authenticated": false,
  "botId": 8580844483,
  "botUsername": "affiliatefm_bot"
}
```

### Детали /zyte-parse

**Response (авторизован):**
```json
{
  "authenticated": true,
  "user": {
    "id": 743045386,
    "username": "under_protect",
    "firstName": "Alex"
  },
  "usage": {
    "parses": {
      "used": 0,
      "limit": 10,
      "remaining": 10
    },
    "resetsAt": "2026-01-28T23:59:59.999Z"
  }
}
```

### JWT Token структура

**Header:**
```json
{"alg":"HS256","typ":"JWT"}
```

**Payload:**
```json
{
  "user": {
    "id": 743045386,
    "first_name": "Alex",
    "last_name": "Nikole",
    "username": "under_protect",
    "photo_url": "https://t.me/i/userpic/...",
    "auth_date": 1769524994
  },
  "iat": 1769524996,
  "exp": 1770129796  // ~7 дней
}
```

### IP адреса google-proxy

Проверенные IP от их сервиса:
- `66.249.93.38`
- `66.249.93.37`
- `66.249.93.41`

Все резолвятся в `google-proxy-66-249-93-XX.google.com`

### Защита от abuse

Они детектят и блокируют сайты которые:
- Показывают IP/headers (httpbin, ifconfig.me, whatismybrowser)
- Возвращают информацию о боте

### 🔑 ГЛАВНЫЙ ВОПРОС: Как получают google-proxy IP?

**Гипотезы:**
1. AWS Lambda вызывает какой-то Google сервис который имеет google-proxy IP
2. У них есть доступ к приватному Google API
3. Партнёрство с Google/DataForSEO
4. Какой-то undocumented Google endpoint

**Что НЕ работает:**
- ❌ Google Apps Script — даёт `194.34.105.215` (не Google)
- ❌ Google App Engine — даёт `*.googleusercontent.com`
- ❌ Google Cloud Functions — даёт `*.googleusercontent.com`
- ❌ Google Cloud Run — даёт `*.googleusercontent.com`

**Что работает для google-proxy IP:**
- ✅ Google Sheets IMPORTDATA — `66.102.x.x` (но нельзя установить UA)
- ✅ affiliate.fm API — `66.249.x.x` (КАК?!)

---

## 28. 🚨🔥 ПРОРЫВ: Google Translate Proxy = РЕШЕНИЕ! (2026-01-28)

### Гипотеза Alex

Alex предположил: "разве они получают гугл прокси апи не через прокси гугл транслейтор?"

### Проверка

**Тест 1: IP через Google Translate**
```bash
$ curl -sS -L "https://icanhazip-com.translate.goog/?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
74.125.210.169

$ host 74.125.210.169
google-proxy-74-125-210-169.google.com
```

**БИНГО!** Тот же `google-proxy-*.google.com` паттерн что у affiliate.fm!

### Формат URL

```
https://{domain-with-dashes}.translate.goog/{path}?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en
```

Пример: `example.com/page` → `example-com.translate.goog/page?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en`

### Тест на cloaked сайтах

**Тест 2: best10reviews.com**
```bash
# Напрямую - показывает старый контент
$ curl -sS -L "https://best10reviews.com" | grep -oE '202[0-9]' | sort | uniq -c
  47 2020
  12 2021

# Через translate.goog - CLOAKED CONTENT!
$ curl -sS -L "https://best10reviews-com.translate.goog/?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en" | grep -oE '202[4-6]'
2026
```

**Тест 3: techradar.com**
```bash
$ curl -sS -L "https://techradar-com.translate.goog/best?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en" | grep -oE '2026'
2026
2026
2026
```

### ДОКАЗАТЕЛЬСТВО

| Источник | URL | Контент | Год |
|----------|-----|---------|-----|
| Прямой запрос | best10reviews.com | User версия | 2020-2021 |
| Google Translate | best10reviews-com.translate.goog | **CLOAKED!** | **2026** |
| affiliate.fm | api.affiliate.fm/googlebot-view | CLOAKED! | 2026 |

### User-Agent через translate.goog

```bash
$ curl -sS -L "https://httpbin-org.translate.goog/headers?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en" | grep User-Agent
"User-Agent": "curl/8.7.1,gzip(gfe)"
```

Google добавляет `,gzip(gfe)` к нашему UA. Но сайты всё равно отдают cloaked контент потому что:
1. **IP = google-proxy** (доверенный)
2. **rDNS = *.google.com** (верификация)

### Ограничения

1. Google блокирует **Googlebot UA** в translate.goog (ошибка "Can't reach website")
2. Но обычный Chrome UA работает!
3. Сайты доверяют по **IP**, а не по UA

### Вывод

**affiliate.fm скорее всего использует Google Translate Website proxy!**

Их Lambda вызывает `{domain}.translate.goog` URL и получает:
- IP: `66.249.x.x` или `74.125.x.x` → `google-proxy-*.google.com`
- Сайты видят Google IP → отдают cloaked content
- Никакого специального API не нужно!

### Реализация для SEO-Pocket

```python
def get_cloaked_content(url: str) -> str:
    """Fetch cloaked content via Google Translate proxy."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain_with_dashes = parsed.netloc.replace(".", "-")
    path = parsed.path or "/"
    query = parsed.query

    translate_url = f"https://{domain_with_dashes}.translate.goog{path}"
    translate_url += f"?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en"
    if query:
        translate_url += f"&{query}"

    # Fetch through Google Translate
    response = httpx.get(translate_url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    })

    # Clean Google Translate wrapper
    html = response.text
    # Remove Google Translate scripts/UI
    # ... cleanup code ...

    return html
```

---

## 29. Следующие шаги

1. ✅ **НАЙДЕНО**: Google Translate proxy = источник google-proxy IP
2. ✅ Создать сервис `google_translate_proxy.py` для SEO-Pocket
3. ✅ Обновить `fetcher.py` с новым методом `translate_goog`
4. ✅ Очистка HTML от Google Translate wrapper
5. [ ] Тестирование на casino сайтах (Cloudflare)
6. [ ] Сравнение с affiliate.fm результатами

---

## 30. ИТОГОВАЯ СВОДКА (2026-01-28)

### Что мы узнали:

1. **affiliate.fm использует Google Translate Website Proxy** для получения cloaked content
2. **Формат URL**: `https://{domain-with-dashes}.translate.goog/{path}?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en`
3. **IP**: `74.125.x.x` или `66.249.x.x` → rDNS: `google-proxy-*.google.com`
4. **Сайты доверяют по IP**, а не по User-Agent!

### Текущие функции SEO-Pocket:

| Функция | Endpoint | Статус | Источник данных |
|---------|----------|--------|-----------------|
| HTML как юзер | `/api/googlebot-view?mode=user` | ✅ | Playwright + Chrome UA |
| HTML как Googlebot | `/api/googlebot-view?mode=bot` | ✅ ОБНОВЛЕНО | Google Translate (.translate.goog) |
| SEO метаданные | `/api/analyze` | ✅ | Парсинг HTML |
| Google Canonical | `/api/analyze` | ✅ | DataForSEO |
| Даты индексации | `/api/analyze` | ⚠️ | Wayback (не Google!) |
| Hreflang/Alternate | `/api/analyze` | ✅ | Парсинг HTML |
| Cloaking detection | `/api/analyze?detect_cloaking=true` | ✅ | Сравнение bot vs user |

### TODO для полного паритета с affiliate.fm:

1. **Даты из Google** — affiliate.fm получает через `/canonical` endpoint (firstIndexed, lastIndexed)
2. **Кросс-доменный canonical** — они определяют canonical на другом домене (it.com → recoveryforall.ca)
3. **Google Cache** — они имеют `/google-cache` endpoint

### Файлы изменены:

- `backend/services/fetcher.py` — добавлен метод `translate_goog` (CLOAKED!)
- `backend/services/google_translate_proxy.py` — новый сервис (альтернатива)
- `backend/services/affiliate_fm.py` — интеграция их API (backup)
- `RESEARCH_AFFILIATE_FM.md` — эта документация

### Ключевые открытия:

```
affiliate.fm IP: 66.249.93.41 → google-proxy-66-249-93-41.google.com
Google Translate IP: 74.125.210.169 → google-proxy-74-125-210-169.google.com

ЭТО ОДИН И ТОТ ЖЕ МЕХАНИЗМ!
```

---

## 31. 🔍 ИССЛЕДОВАНИЕ: Откуда affiliate.fm берёт даты? (2026-01-28)

### Тестирование /canonical endpoint

| Сайт | affiliate.fm firstIndexed | Wayback first | Google SERP dates |
|------|---------------------------|---------------|-------------------|
| twitter.com | 2004-11-04 | 2006 | разные |
| facebook.com | 2004-11-04 | 2004 | разные |
| chatgpt.com | **2022-12-15** | 2022-12-03 | 2022-04-03 (!!) |
| stripe.com | 2005-07-03 | 2000-03-01 | разные |

### ❌ Гипотеза "Google SERP бинарный поиск" - ОПРОВЕРГНУТА!

Проверка показала что **Google SERP с фильтром дат НЕ совпадает** с данными affiliate.fm:

```
chatgpt.com:
- Google SERP показывает результаты от 3 апреля 2022 (!)
- Wayback Machine: первый снапшот 3 декабря 2022
- affiliate.fm: 15 декабря 2022
```

Google SERP даёт **неточные/фейковые** даты (показывает апрель 2022 для chatgpt.com когда ChatGPT запустился в ноябре 2022).

### Возможные источники дат affiliate.fm:

1. **Приватный Google API** - доступ к данным индексации
2. **Common Crawl** - публичный веб-архив с датами
3. **Собственный краулер** - записывают когда впервые увидели страницу
4. **Комбинация источников** - Wayback + эвристики

### Что известно точно:

- Старые сайты (до 2005) показывают **2004-11-04** - это "начало данных"
- Новые сайты показывают даты близкие к Wayback
- `published` дата - это дата последнего обновления контента

### Вывод для SEO-Pocket:

**НЕ ЯСНО** точный источник дат affiliate.fm.

**Временное решение**: использовать Wayback Machine API:
```python
# Wayback CDX API для первого снапшота
curl "https://web.archive.org/cdx/search/cdx?url=domain.com&output=json&limit=1&from=2000"
```

**TODO**: Продолжить исследование источника дат.

---

## 32. 🔥 ПОЛНЫЙ API АУДИТ affiliate.fm (2026-01-28)

### Все инструменты на сайте

| Инструмент | URL | Доступ | Статус |
|------------|-----|--------|--------|
| Google-selected Canonical | `/tools/google-selected-canonical/` | Subscribers | Released |
| Googlebot View | `/tools/googlebot-view/` | Subscribers | Released |
| Google Cache View | `/tools/google-cache/` | Subscribers | **Experimental/Unstable** |
| AI Content Rewriter | `/tools/ai-content-rewriter/` | Open Source | Released |
| Astro Content AI Translator | `/tools/ai-translator/` | Open Source | Released |
| Website Core Template | `/tools/website-core/` | Open Source | Released |
| Astro Content AI Enhancer | `/tools/ai-enhancer/` | Open Source | Released |

### Все API endpoints (ПОЛНЫЙ СПИСОК)

#### 1. `/googlebot-view` — HTML как Googlebot
```bash
# Без авторизации (кэшированные)
GET https://api.affiliate.fm/googlebot-view?url=URL&lang=en

# С авторизацией (любые)
GET https://api.affiliate.fm/googlebot-view?url=URL&lang=en
Authorization: Bearer JWT

# С redirect chain
GET https://api.affiliate.fm/googlebot-view?url=URL&chain=1&lang=en
Authorization: Bearer JWT
```

**Response (HTML):**
```html
<!doctype html><html>...</html>
```

**Response (chain=1):**
```json
{
  "success": true,
  "url": "https://example.com/",
  "startDomain": "example.com",
  "finalDomain": "example.com",
  "redirectCount": 0,
  "chain": [{"url": "https://example.com/", "status": 200}],
  "cached": true
}
```

**Response (ошибка):**
```json
{"success": false, "error": "Site blocks bot traffic", "url": "...", "cached": true}
```

#### 2. `/canonical` — Google Canonical + даты
```bash
GET https://api.affiliate.fm/canonical?url=URL&lang=en
Authorization: Bearer JWT
```

**Response:**
```json
{
  "url": "https://github.com",
  "googleCanonical": "https://github.com/",
  "domain": "github.com",
  "cached": true,
  "firstIndexed": {
    "timestamp": 1099555200,
    "date": "2004-11-04T08:00:00.000Z"
  },
  "published": {
    "timestamp": 1769414400,
    "date": "2026-01-26T08:00:00.000Z"
  },
  "relatedDomains": ["digital.gov", "globaldata.com"]
}
```

**Поля:**
- `googleCanonical` — URL который Google считает каноническим
- `firstIndexed` — дата первой индексации (источник неизвестен!)
- `published` — дата публикации/обновления контента
- `relatedDomains` — связанные домены (откуда?)

#### 3. `/google-cache` — HTML из Google Cache
```bash
GET https://api.affiliate.fm/google-cache?url=URL&lang=en
Authorization: Bearer JWT

# internal mode
GET https://api.affiliate.fm/google-cache?url=URL&lang=en&internal=1
```

**Response:**
```html
<!DOCTYPE html><html lang="en">
<head><base href="https://example.com"><title>affiliate.fm</title>
<!-- Google Cache version of the page -->
</head>
<body>...</body>
</html>
```

**Примечание:** В UI написано "Unstable Tool - Requires manual server restart every hour"

#### 4. `/zyte-parse` — Zyte API прокси для Content Rewriter
```bash
# Проверка лимитов (GET)
GET https://api.affiliate.fm/zyte-parse?url=URL&lang=en
Authorization: Bearer JWT

# Парсинг (POST)
POST https://api.affiliate.fm/zyte-parse
Authorization: Bearer JWT
Content-Type: application/json
{"url": "https://example.com"}
```

**Response (GET - лимиты):**
```json
{
  "authenticated": true,
  "user": {"id": 743045386, "username": "under_protect", "firstName": "Alex"},
  "usage": {
    "parses": {"used": 1, "limit": 10, "remaining": 9},
    "resetsAt": "2026-01-28T23:59:59.999Z"
  }
}
```

**Response (POST - парсинг):**
```json
{
  "success": true,
  "url": "https://example.com",
  "title": "Example Domain",
  "description": "",
  "html": "<h1>Example Domain</h1>...",
  "stats": {"duration": 4422},
  "usage": {"parses": {"used": 2, "limit": 10, "remaining": 8}, "resetsAt": "..."}
}
```

#### 5. `/telegram-auth` — Проверка авторизации
```bash
GET https://api.affiliate.fm/telegram-auth
```

**Response (не авторизован):**
```json
{
  "authenticated": false,
  "botId": 8580844483,
  "botUsername": "affiliatefm_bot"
}
```

### Лимиты и квоты

| Ресурс | Лимит | Период |
|--------|-------|--------|
| Zyte parses | 10 | День |
| AI Rewrites | 10 | День |
| Googlebot View | Unlimited? | - |
| Canonical | Unlimited? | - |
| Google Cache | Unlimited? | - |

### Кэширование

- Header `x-cache: HIT` или `x-cache: MISS`
- Кэшированные результаты доступны БЕЗ авторизации
- Новые URL требуют авторизации

### Инфраструктура

**Подтверждено из headers:**
```
x-amzn-requestid: ...
x-amz-apigw-id: ...
```

**Вывод:** AWS API Gateway + AWS Lambda

### JWT Token

**Время жизни:** ~7 дней
**Формат:**
```json
{
  "user": {
    "id": 743045386,
    "first_name": "Alex",
    "last_name": "Nikole",
    "username": "under_protect",
    "photo_url": "https://t.me/i/userpic/...",
    "auth_date": 1769524994
  },
  "iat": 1769524996,
  "exp": 1770129796
}
```

### Защита от abuse

Сайты показывающие IP/headers блокируются:
- httpbin.org/headers — `Site blocks bot traffic`
- icanhazip.com — Иногда работает, иногда нет
- whatismybrowser.com — Блокируется

---

## 33. Сравнение SEO-Pocket vs affiliate.fm

| Функция | affiliate.fm | SEO-Pocket | Статус |
|---------|-------------|------------|--------|
| Googlebot View | ✅ | ✅ | Google Translate proxy |
| Google Canonical | ✅ | ✅ | DataForSEO |
| First/Last Indexed | ✅ | ⚠️ | Wayback (не точно!) |
| Related Domains | ✅ | ❌ | TODO |
| Google Cache | ✅ | ❌ | TODO |
| Redirect Chain | ✅ | ✅ | Playwright |
| Cloaking Detection | ❌ | ✅ | Bot vs User diff |
| AI Content Rewriter | ✅ (Zyte) | ❌ | Not planned |

### TODO для паритета:

1. [ ] Найти источник дат first/last indexed (не Wayback!)
2. [ ] Related domains - откуда берут?
3. [ ] Google Cache endpoint
4. [ ] Улучшить определение canonical

