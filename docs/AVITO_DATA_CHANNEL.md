# Avito data channel — readiness criteria (Phase 4.1)

Phase 4.0 ships stubs only. Production fetch for Russia requires a **legal data channel** agreed in writing.

## Not acceptable for production

- Scraping avito.ru HTML or unofficial mobile APIs
- Using Avito seller API to monitor the public marketplace catalog
- Mixing Avito HTTP calls in the same batch/cache as Kufar

## Acceptable channels

| Channel | Notes |
|---------|--------|
| Partner JSON/CSV feed | Periodic snapshot or push; preferred for v1 |
| Licensed aggregator API | Contract, rate limits, SLA |
| Official marketplace data product | If Avito or partner offers catalog export |

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

1. `AVITO_FEED_URL` (+ auth) configured on server
2. `marketplace/avito.py` implements `fetch_for_key` against feed
3. Staging: 1–2 users with `country=ru`, city set, `AVITO_ENABLED=true`
4. Logs show separate `poll avito …` lines without Kufar errors
5. Rollout to prod; BY users unchanged

## Config (Phase 4.0)

```env
AVITO_ENABLED=false
AVITO_CHECK_INTERVAL=420
AVITO_VIP_CHECK_INTERVAL=60
AVITO_FETCH_CACHE_TTL_SECONDS=30
```

Set `AVITO_ENABLED=true` only after the checklist above.

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

