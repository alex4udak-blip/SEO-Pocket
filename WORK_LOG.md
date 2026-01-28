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
