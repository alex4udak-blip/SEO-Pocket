# SEO-Pocket — Результаты глубокой разведки лазейки Google

## Итоговый вывод (100% уверенность)

**ЛАЗЕЙКА = Google Rich Results Test + Headless Browser (Playwright/Puppeteer)**

affiliate.fm и любой другой сервис получает rendered HTML через автоматизацию браузера на странице Rich Results Test. **НЕ существует "секретного API"** — только scraping UI.

---

## Полный анализ всех вариантов

### ❌ ИСКЛЮЧЕНО: Официальный Google API

| API | Rendered HTML | Статус |
|-----|---------------|--------|
| Search Console API (URL Inspection) | **НЕТ** | Только метаданные индексации |
| Mobile-Friendly Test API | **ЗАКРЫТ** | Deprecated December 2023 |
| PageSpeed Insights API | **НЕТ** | Только метрики производительности |
| AMP Test API | **НЕТ** | Только валидация AMP |

**Google официально НЕ предоставляет API для получения rendered HTML.**

> "You can click 'View tested page' to see rendered HTML... However, presently only the status of the version in the Google index is available; you cannot test the indexability of a live URL through the API."
> — Google Documentation

---

### ✅ ПОДТВЕРЖДЕНО: Rich Results Test Internal RPC

**Механизм работы:**

```
1. POST /_/SearchConsoleUi/data/batchexecute?rpcids=MrNfbc
   Body: f.req=[[["MrNfbc","[\"URL\"]",null,"generic"]]]
   → Получаем test_id (например: "neYGu0YTXbd3teEoMGitPg")

2. Ждём завершения сканирования (poll или webhook)

3. POST /_/SearchConsoleUi/data/batchexecute?rpcids=YDPhmb
   Body: f.req=[[["YDPhmb","[\"TEST_ID\"]",null,"generic"]]]
   → Получаем rendered HTML
```

**Проблема:** YDPhmb требует Google cookies (SID, SSID, etc.) для авторизации.

**Решение:** Playwright с залогиненным Google аккаунтом.

---

### Почему affiliate.fm такой быстрый (2-3 сек)?

**Анализ:**
- Rich Results Test UI занимает 5-15 секунд на полное сканирование
- affiliate.fm отвечает за 2-3 секунды

**Возможные объяснения:**

1. **Кэширование** — для популярных сайтов результат уже в кэше
2. **Оптимизированный Playwright** — параллельные сессии, pre-warmed browsers
3. **Агрессивное кэширование на стороне API** — результаты сохраняются на часы/дни
4. **Race condition** — начинает возвращать partial data до полного завершения

**Тест:** Когда я проверял fresh URL (cut-to.link), affiliate.fm тоже работал быстро — значит либо кэш Google, либо оптимизация Playwright.

---

## Техническая реализация (рекомендация)

### Подход 1: Playwright + Rich Results Test (PRIMARY)

```python
from playwright.async_api import async_playwright
import asyncio

class GooglebotViewFetcher:
    """
    Получает rendered HTML через Google Rich Results Test.
    Требует залогиненный Google аккаунт.
    """

    async def fetch(self, url: str) -> dict:
        async with async_playwright() as p:
            # Используем persistent context с сохранёнными cookies
            browser = await p.chromium.launch_persistent_context(
                user_data_dir="./google_profile",
                headless=True
            )
            page = await browser.new_page()

            try:
                # Шаг 1: Открыть Rich Results Test с URL
                test_url = f"https://search.google.com/test/rich-results?url={url}"
                await page.goto(test_url, wait_until="networkidle")

                # Шаг 2: Дождаться результата
                await page.wait_for_selector(
                    'text="Посмотреть проверенную страницу"',
                    timeout=30000
                )

                # Шаг 3: Кликнуть и получить HTML
                await page.click('text="Посмотреть проверенную страницу"')
                await page.wait_for_selector('[class*="html"]', timeout=10000)

                # Шаг 4: Извлечь данные
                html = await page.evaluate('''
                    () => {
                        // Найти панель с HTML
                        const codeLines = document.querySelectorAll('[class*="line"]');
                        return Array.from(codeLines).map(l => l.textContent).join('\\n');
                    }
                ''')

                return {
                    "success": True,
                    "html": html,
                    "source": "rich_results_test"
                }

            finally:
                await browser.close()
```

### Подход 2: Direct RPC Call (если получим cookies)

```python
import httpx

async def fetch_via_rpc(url: str, cookies: dict) -> str:
    """
    Прямой вызов Google RPC endpoint.
    Требует валидные Google cookies.
    """

    # Шаг 1: Отправить URL на проверку
    async with httpx.AsyncClient(cookies=cookies) as client:
        # MrNfbc - начать проверку
        response = await client.post(
            "https://search.google.com/_/SearchConsoleUi/data/batchexecute",
            params={
                "rpcids": "MrNfbc",
                "source-path": "/test/rich-results",
                "hl": "ru"
            },
            data={
                "f.req": f'[[["MrNfbc","[\\"{url}\\"]",null,"generic"]]]'
            },
            headers={
                "content-type": "application/x-www-form-urlencoded"
            }
        )

        # Парсим test_id из ответа
        # Response: [["wrb.fr","MrNfbc","[\"URL\",5]",null,null,null,"generic"]]
        test_id = parse_test_id(response.text)

        # Шаг 2: Получить результат (после завершения)
        # Нужно poll-ить или ждать
        await asyncio.sleep(10)  # Упрощённо

        # YDPhmb - получить rendered HTML
        html_response = await client.post(
            "https://search.google.com/_/SearchConsoleUi/data/batchexecute",
            params={
                "rpcids": "YDPhmb",
                "source-path": "/test/rich-results/result",
                "hl": "ru"
            },
            data={
                "f.req": f'[[["YDPhmb","[\\"{test_id}\\"]",null,"generic"]]]'
            }
        )

        return parse_html_from_response(html_response.text)
```

---

## RPC ID Reference

| RPC ID | Назначение | Параметры |
|--------|-----------|-----------|
| `MrNfbc` | Начать проверку URL | `["URL"]` |
| `YDPhmb` | Получить rendered HTML | `["TEST_ID"]` |
| `ueowNe` | Неизвестно | - |
| `HZPzjb` | Неизвестно | - |
| `C4lTm` | Неизвестно | - |
| `zUbeBb` | Неизвестно | - |
| `OFNzWe` | Неизвестно | - |
| `bbONqe` | Неизвестно | - |

---

## Fallback стратегия

```
Priority 1: Rich Results Test (Playwright)
    ↓ если не работает
Priority 2: Google Cache scraping
    ↓ если нет в кэше
Priority 3: Playwright + Googlebot UA
    ↓ если блокируют
Priority 4: Wayback Machine
```

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Google меняет UI Rich Results | Средняя | Fallback selectors, мониторинг |
| Rate limiting | Высокая | Proxy rotation, delays |
| CAPTCHA | Средняя | Residential proxies |
| Account ban | Низкая | Использовать throwaway аккаунты |

---

## Выводы для реализации

1. **Нет секретного API** — только UI scraping
2. **Playwright — единственный надёжный путь** для Rich Results Test
3. **Нужен Google аккаунт** для YDPhmb запросов
4. **Кэширование критично** — не делать лишних запросов
5. **Multi-source fallback** — для 100% надёжности

---

## Следующие шаги

1. [ ] Создать Playwright script для Rich Results Test
2. [ ] Настроить persistent Google session
3. [ ] Реализовать кэширование результатов
4. [ ] Добавить fallback sources
5. [ ] Создать FastAPI backend
6. [ ] Frontend с результатами

---

*Последнее обновление: 27 января 2026*
