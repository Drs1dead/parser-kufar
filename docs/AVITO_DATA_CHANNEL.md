# Avito data channel — readiness criteria (Phase 4.1 / 4.2)

Phase 4.0 ships stubs only. Production fetch for Russia requires a **legal data channel** agreed in writing.

## Not acceptable for production

- Scraping avito.ru HTML or unofficial mobile APIs **inside the bot**
- Using Avito seller API to monitor the public marketplace catalog
- Mixing Avito HTTP calls in the same batch/cache as Kufar

## Acceptable channels

| Channel | Notes |
|---------|--------|
| Self-hosted search API (Phase 4.2) | Per-key `GET` collector; primary prod path |
| Partner JSON/CSV feed (Phase 4.1) | Snapshot fallback if search URL unset |
| Licensed aggregator API | Contract, rate limits, SLA |
| Official marketplace data product | If Avito or partner offers catalog export |

Self-hosted collector (отдельный сервис) реализует `AVITO_SEARCH_URL` — бот только HTTP-клиент, без парсинга avito.ru.

## Minimum fields per listing

- `id` — stable listing id
- `title`
- `price_rub` — integer, RUB
- `url` — canonical link
- `city` / `region` — match `avito_city_id` / `avito_region_id` in bot DB
- `photos` — list of URLs
- `description` — text (optional for matching; required for VIP cards)
- `published_at` — ISO timestamp
- `category` — mappable to bot `product_category`

## Operational requirements

- Documented rate limits and retry policy
- Feed freshness SLA (e.g. listings no older than N minutes)
- Incident contact and changelog for schema breaks
- Staging environment for smoke tests before `AVITO_ENABLED=true`

## Enable checklist

1. `AVITO_SEARCH_URL` (+ auth) configured on server — **primary** (Phase 4.2)
2. Optional fallback: `AVITO_FEED_URL` if search URL unset (Phase 4.1)
3. `marketplace/avito.py` implements `fetch_for_key` against search or feed
4. Staging: 1–2 users with `country=ru`, city set, `AVITO_ENABLED=true`
5. Logs show separate `poll avito …` lines without Kufar errors
6. Rollout to prod; BY users unchanged

## Config (Phase 4.0)

```env
AVITO_ENABLED=false
AVITO_CHECK_INTERVAL=420
AVITO_VIP_CHECK_INTERVAL=60
```

Set `AVITO_ENABLED=true` only after the checklist below.

## Как получить данные (API / фид)

**Публичного API Avito «слушать витрину» нет.** Официальный API Avito — для **своих** объявлений продавца (управление листингами), не для мониторинга каталога чужих телефонов.

Варианты для бота:

| Вариант | Что нужно |
|---------|-----------|
| Self-hosted search API | `AVITO_SEARCH_URL` — collector с `GET /search?city_id=…` (Фаза 4.2) |
| Партнёрский JSON feed | URL + токен; fallback если search URL пуст (Фаза 4.1) |
| Локальный тест | `AVITO_DEV_MOCK=true` — без HTTP, файл `geo/avito_mock_ads.json` |

Настройка prod search (primary):

```env
AVITO_ENABLED=true
AVITO_DEV_MOCK=false
AVITO_SEARCH_URL=https://your-collector.example/avito/search
AVITO_FEED_AUTH=Bearer <token>   # Authorization для collector
FEED_REFRESH_SECONDS=30            # TTL кэша fetch по FetchKey (Kufar + Avito)
```

Fallback snapshot feed (если `AVITO_SEARCH_URL` пуст):

```env
AVITO_FEED_URL=https://your-partner.example/avito-feed.json
```

Формат ответа feed — массив `[{...}]` или объект `{"ads": [...]}`. Пример записи: [`geo/avito_feed_sample.json`](geo/avito_feed_sample.json).

Если партнёра ещё нет — оставьте `AVITO_ENABLED=true` + `AVITO_DEV_MOCK=true` для smoke-теста UI и poller.

## Local dev mock (end-to-end без фида)

Для smoke-теста UI + poller + карточки «Открыть на Avito» без HTTP к avito.ru:

```env
AVITO_ENABLED=true
AVITO_DEV_MOCK=true
```

Данные: [`geo/avito_mock_ads.json`](geo/avito_mock_ads.json) — фильтрация по `FetchKey` (город, категория, модель, память), как catalog path на Kufar.

Шаги в боте:

1. Страна → Россия (возврат на главную; город — кнопка «Город»)
2. Город → Москва / Смоленск
3. Товары → модель (например iPhone 15), память
4. Включить уведомления

При старте бота в логах: `AVITO_DEV_MOCK=true — … mock_ads.json`.

## Search API (Фаза 4.2)

Per-key запрос, аналог Kufar `catalog_search_params` → search-api.

**Endpoint:** `AVITO_SEARCH_URL` (полный URL handler, например `https://collector.example/avito/search`).

**Method:** `GET`

**Query params** (из `FetchKey` через [`avito_catalog.search_params_from_key`](avito_catalog.py)):

| Param | Источник | Пример |
|-------|----------|--------|
| `city_id` | `geo_b` | `637640` |
| `region_id` | `geo_a` (если задан) | `637640` |
| `category` | категория | `phones` |
| `models` | models tuple, comma-separated | `iphone 15,iphone 15 pro` |
| `memory_gb` | memories (только phones) | `256` или `128,256` |

**Response:** как feed 4.1 — массив `[{...}]` или `{"ads": [...]}`. Поля — «Minimum fields».

**Auth:** `AVITO_FEED_AUTH` → `Authorization` header.

**Retry:** 5xx/429/network — `AVITO_FEED_RETRIES`, `AVITO_FEED_RETRY_DELAY`.

Collector отвечает **уже отфильтрованным** списком по ключу; бот только нормализует (`normalize_feed_ad`), без `filter_ads_for_key`.

Кэш per `FetchKey` в poller (`FEED_REFRESH_SECONDS`) — один HTTP search на уникальный ключ за TTL.

### Prod checklist (search)

```env
AVITO_ENABLED=true
AVITO_DEV_MOCK=false
AVITO_SEARCH_URL=https://collector.example/avito/search
# AVITO_FEED_AUTH=Bearer <token>
FEED_REFRESH_SECONDS=30
```

## JSON feed format (Фаза 4.1 — fallback)

Поддерживаются два корневых формата:

```json
[{ "id": "...", "title": "...", "price_rub": 75000, "url": "...", ... }]
```

```json
{ "ads": [ { "id": "...", ... } ] }
```

Поля записи — как в секции «Minimum fields» выше. При snapshot feed — фильтрация по `FetchKey` на стороне бота.

Пример: [`geo/avito_feed_sample.json`](geo/avito_feed_sample.json).

### Prod checklist (feed fallback)

```env
AVITO_ENABLED=true
AVITO_DEV_MOCK=false
# AVITO_SEARCH_URL=   # пуст — используется feed
AVITO_FEED_URL=https://partner.example/avito-feed.json
# AVITO_FEED_AUTH=Bearer <token>
FEED_REFRESH_SECONDS=30
```

- Один HTTP GET на снимок feed раз в `FEED_REFRESH_SECONDS`
- Retry на 5xx/429/network (`AVITO_FEED_RETRIES`)
- RU anti-junk: [`filters_avito.py`](filters_avito.py)

