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
