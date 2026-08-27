"""Mock и JSON feed Avito (без парсинга avito.ru)."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import aiohttp

from config import (
    AVITO_FEED_AUTH,
    AVITO_FEED_FILE,
    AVITO_FEED_RETRIES,
    AVITO_FEED_RETRY_DELAY,
    AVITO_FEED_TIMEOUT_SECONDS,
    AVITO_FEED_URL,
    FEED_REFRESH_SECONDS,
)
from filters import _normalize_memory_selection, memory_matches_ad
from marketplace.keys import FetchKey
from marketplace.types import CURRENCY_RUB, SOURCE_AVITO
from product_catalog import is_phones_category, normalize_category

log = logging.getLogger(__name__)

AVITO_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

_MOCK_PATH = Path(__file__).resolve().parent / "geo" / "avito_mock_ads.json"
_mock_cache: list[dict] | None = None
_feed_snapshot: tuple[float, list[dict]] | None = None


def _load_mock_ads() -> list[dict]:
    global _mock_cache
    if _mock_cache is not None:
        return _mock_cache
    try:
        raw = json.loads(_MOCK_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        log.warning("avito mock file missing path=%s: %s", _MOCK_PATH, exc)
        _mock_cache = []
        return _mock_cache
    if not isinstance(raw, list):
        log.warning("avito mock invalid format path=%s", _MOCK_PATH)
        _mock_cache = []
        return _mock_cache
    _mock_cache = [item for item in raw if isinstance(item, dict)]
    log.info("avito mock loaded ads=%d path=%s", len(_mock_cache), _MOCK_PATH)
    return _mock_cache


def normalize_feed_ad(raw: dict) -> dict | None:
    title = str(raw.get("title") or "").strip()
    link = str(raw.get("url") or raw.get("link") or "").strip()
    if not title or not link:
        return None
    price = raw.get("price_rub", raw.get("price"))
    if price is not None:
        try:
            price = int(price)
        except (TypeError, ValueError):
            price = None
    city = str(raw.get("city") or "").strip()
    region = str(raw.get("region") or "").strip()
    location = str(raw.get("location") or "").strip()
    if not location:
        location = f"{region}, {city}" if region and city else region or city
    photos = raw.get("photos") or raw.get("photo_urls") or []
    if not isinstance(photos, list):
        photos = []
    return {
        "ad_id": str(raw.get("id") or link),
        "title": title,
        "price": price,
        "location": location,
        "summary": str(raw.get("summary") or "").strip(),
        "description": str(raw.get("description") or "").strip(),
        "link": link.split("?")[0],
        "list_time": raw.get("published_at") or raw.get("list_time"),
        "photo_urls": [str(p) for p in photos if p],
        "region_id": str(raw.get("region_id") or "").strip(),
        "city_id": str(raw.get("city_id") or "").strip(),
        "category": normalize_category(raw.get("category")),
        "source": SOURCE_AVITO,
        "currency": CURRENCY_RUB,
    }


def _title_matches_models(title: str, models: tuple[str, ...]) -> bool:
    if not models:
        return False
    hay = title.lower().replace("ё", "е")
    for model in models:
        token = model.lower().replace("ё", "е").strip()
        if token and token in hay:
            return True
    return False


def _geo_matches(raw: dict, region_id: str, city_id: str) -> bool:
    if not city_id:
        return True
    raw_city = str(raw.get("city_id") or "").strip()
    raw_region = str(raw.get("region_id") or "").strip()
    if raw_city and raw_city == city_id:
        return True
    if raw_region and region_id and raw_region == region_id and raw_city == city_id:
        return True
    return False


def filter_ads_for_key(raw_items: list[dict], key: FetchKey) -> list[dict]:
    """Локальная фильтрация листинга по FetchKey (как catalog facets на Kufar)."""
    source, category, geo_a, geo_b, models, memories = key
    if source != SOURCE_AVITO:
        return []
    region_id = str(geo_a or "").strip()
    city_id = str(geo_b or geo_a or "").strip()
    cat = normalize_category(category)
    out: list[dict] = []
    selected_mem = _normalize_memory_selection(list(memories)) if memories else set()

    for raw in raw_items:
        if normalize_category(raw.get("category")) != cat:
            continue
        if not _geo_matches(raw, region_id, city_id):
            continue
        if not _title_matches_models(str(raw.get("title") or ""), models):
            continue
        ad = normalize_feed_ad(raw)
        if ad is None:
            continue
        if is_phones_category(cat) and selected_mem:
            if not memory_matches_ad(ad, selected_mem):
                continue
        out.append(ad)

    log.debug(
        "avito filter key=%s matched=%d from=%d",
        (source, cat, region_id, city_id, len(models), list(memories)),
        len(out),
        len(raw_items),
    )
    return out


def fetch_mock_ads_for_key(key: FetchKey) -> list[dict]:
    return filter_ads_for_key(_load_mock_ads(), key)


def _parse_feed_payload(data: object) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        ads = data.get("ads")
        if isinstance(ads, list):
            return [item for item in ads if isinstance(item, dict)]
    log.warning("avito feed unexpected JSON shape")
    return []


def _read_feed_file(path: str) -> list[dict]:
    file_path = Path(path)
    if path.startswith("file://"):
        file_path = Path(path[7:])
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    items = _parse_feed_payload(raw)
    log.info("avito feed file loaded ads=%d path=%s", len(items), file_path)
    return items


def _feed_auth_headers() -> dict[str, str]:
    if not AVITO_FEED_AUTH:
        return {}
    if AVITO_FEED_AUTH.lower().startswith("bearer "):
        return {"Authorization": AVITO_FEED_AUTH}
    return {"Authorization": AVITO_FEED_AUTH}


async def _fetch_feed_http(session: aiohttp.ClientSession) -> list[dict]:
    if not AVITO_FEED_URL:
        return []
    headers = dict(_feed_auth_headers())
    last_err: str | None = None
    for attempt in range(1, AVITO_FEED_RETRIES + 1):
        try:
            async with session.get(
                AVITO_FEED_URL,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=AVITO_FEED_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status >= 500 or resp.status == 429:
                    body = (await resp.text())[:200]
                    last_err = f"status={resp.status} {body}"
                    log.warning(
                        "avito feed retry %s attempt=%s/%s",
                        last_err,
                        attempt,
                        AVITO_FEED_RETRIES,
                    )
                    if resp.status == 429 and attempt < AVITO_FEED_RETRIES:
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                await asyncio.sleep(float(retry_after))
                            except ValueError:
                                pass
                    if attempt < AVITO_FEED_RETRIES:
                        await asyncio.sleep(AVITO_FEED_RETRY_DELAY * attempt)
                    continue
                if resp.status != 200:
                    log.error("avito feed failed status=%s url=%s", resp.status, AVITO_FEED_URL)
                    return []
                data = await resp.json(content_type=None)
                items = _parse_feed_payload(data)
                log.info("avito feed http loaded ads=%d url=%s", len(items), AVITO_FEED_URL)
                return items
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
            last_err = repr(exc)
            log.warning(
                "avito feed network attempt=%s/%s err=%s",
                attempt,
                AVITO_FEED_RETRIES,
                last_err,
            )
        if attempt < AVITO_FEED_RETRIES:
            await asyncio.sleep(AVITO_FEED_RETRY_DELAY * attempt)
    if last_err:
        log.error("avito feed exhausted url=%s err=%s", AVITO_FEED_URL, last_err)
    return []


async def load_feed_snapshot(
    session: aiohttp.ClientSession,
    *,
    force: bool = False,
) -> list[dict]:
    """Загружает полный снимок feed (HTTP или файл) с TTL в памяти."""
    global _feed_snapshot
    now = time.time()
    if (
        not force
        and _feed_snapshot is not None
        and now - _feed_snapshot[0] < FEED_REFRESH_SECONDS
    ):
        return _feed_snapshot[1]

    if AVITO_FEED_URL:
        items = await _fetch_feed_http(session)
    elif AVITO_FEED_FILE:
        items = _read_feed_file(AVITO_FEED_FILE)
    else:
        items = []

    _feed_snapshot = (now, items)
    return items


async def fetch_feed_ads_for_key(
    key: FetchKey,
    session: aiohttp.ClientSession,
) -> list[dict]:
    items = await load_feed_snapshot(session)
    return filter_ads_for_key(items, key)


def reset_feed_snapshot_for_tests() -> None:
    global _feed_snapshot, _mock_cache
    _feed_snapshot = None
    _mock_cache = None
