# SEO-Pocket Work Log

### 2026-01-28 — Zyte API Integration (Cloudflare Bypass)

**Что сделано:**
- Reverse-engineering affiliate.fm - обнаружено что они используют Zyte API для обхода Cloudflare
- Создан документ RESEARCH_AFFILIATE_FM.md с разведданными
- Создан сервис `/backend/services/zyte.py` — клиент Zyte API
- Интегрирован Zyte в SmartFetcher как Strategy 1
- Добавлена проверка _is_blocked_response() для Strategy 0 (Google Translate)
- Добавлен ZYTE_API_KEY в Railway environment variables
- Задеплоено на Railway через CLI

**Результат:**
- Casino сайт `casino-ohne.gaststaette-hillenbrand.de` теперь отдаёт контент
- Стратегия: ZYTE (6662ms)
- PAGE TITLE: "Casinos ohne limit OASIS – die besten Anbieter ohne Sperre in Deutschland 2025"
- H1: "Casino ohne limit oasis 2025"
- HTML LANG: de

**Файлы изменены:**
- `backend/services/zyte.py` (NEW)
- `backend/core/config.py` (zyte_api_key)
- `backend/services/fetcher.py` (Zyte integration)
- `backend/.env` (ZYTE_API_KEY)
- `RESEARCH_AFFILIATE_FM.md` (NEW)

**Проверено на проде:** ✅ awake-fascination-production.up.railway.app

**TODO на следующую сессию:**
- [ ] Понять откуда affiliate.fm берёт cross-domain canonical (it.com → recoveryforall.ca)
- [ ] Оптимизировать порядок стратегий (Zyte дороже Google Translate)
- [ ] Добавить кэширование результатов Zyte

---

### 2026-01-28 (вечер) — Исследование Cloaking Detection

**Проблема обнаружена:**
- Zyte возвращает контент **2025** года (обычная страница)
- affiliate.fm показывает **2026** год (cloaked content для Googlebot)
- Google Rich Results Test подтверждает: реальный Googlebot видит 2026

**Ключевое открытие:**
- Zyte обходит Cloudflare, НО сайты определяют что это НЕ Googlebot
- Сайты используют IP-based cloaking (проверяют Google IP ranges)
- affiliate.fm маркетинг утверждает: "Fetches from Google's actual IP ranges"

**Исследовано:**
1. **Google Rich Results Test** — работает, показывает cloaked content, но нет API
2. **Google URL Inspection API** — только для своих сайтов в Search Console
3. **DataForSEO On-Page API** — позволяет custom UA, но использует свои IP (не Google)
4. **Google Cloud Functions/Run** — используют IP из пула Google, возможно работает

**Google IP диапазоны:**
- Googlebot: `192.178.4-7.x`, `34.x.x.x` (reverse DNS: *.googlebot.com)
- User-triggered fetchers: `142.250.x.x`, `192.178.10-13.x` (*.gae.googleusercontent.com)
- Cloud Run: динамические из пула Google

**Гипотеза:**
affiliate.fm использует Google Cloud (Run/Functions) с Googlebot User-Agent.
Сайты видят Google IP + Googlebot UA → показывают cloaked content.

**Файлы обновлены:**
- `RESEARCH_AFFILIATE_FM.md` — добавлены секции 12-16 с новыми находками

**TODO:**
- [ ] Развернуть Cloud Run функцию для теста
- [ ] Проверить получаем ли cloaked content с GCP IP
- [ ] Если да — интегрировать как Strategy 0
- [ ] Оставить Zyte как fallback для Cloudflare bypass
