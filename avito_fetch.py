"""Mock и будущий feed Avito (без парсинга avito.ru)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from filters import _normalize_memory_selection, memory_matches_ad
from marketplace.keys import FetchKey
from marketplace.types import CURRENCY_RUB, SOURCE_AVITO
from product_catalog import is_phones_category, normalize_category

log = logging.getLogger(__name__)

_MOCK_PATH = Path(__file__).resolve().parent / "geo" / "avito_mock_ads.json"
_mock_cache: list[dict] | None = None


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


def normalize_mock_ad(raw: dict) -> dict | None:
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
    location = f"{region}, {city}" if region and city else region or city
    photos = raw.get("photos") or raw.get("photo_urls") or []
    if not isinstance(photos, list):
        photos = []
    return {
        "ad_id": str(raw.get("id") or link),
        "title": title,
        "price": price,
        "location": location,
        "summary": "",
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


def fetch_mock_ads_for_key(key: FetchKey) -> list[dict]:
    """Локальная фильтрация mock-листинга по FetchKey (как catalog facets на Kufar)."""
    source, category, geo_a, geo_b, models, memories = key
    if source != SOURCE_AVITO:
        return []
    region_id = str(geo_a or "").strip()
    city_id = str(geo_b or geo_a or "").strip()
    cat = normalize_category(category)
    out: list[dict] = []
    selected_mem = _normalize_memory_selection(list(memories)) if memories else set()

    for raw in _load_mock_ads():
        if normalize_category(raw.get("category")) != cat:
            continue
        if not _geo_matches(raw, region_id, city_id):
            continue
        if not _title_matches_models(str(raw.get("title") or ""), models):
            continue
        ad = normalize_mock_ad(raw)
        if ad is None:
            continue
        if is_phones_category(cat) and selected_mem:
            if not memory_matches_ad(ad, selected_mem):
                continue
        out.append(ad)

    log.debug(
        "avito mock key=%s matched=%d",
        (source, cat, region_id, city_id, len(models), list(memories)),
        len(out),
    )
    return out
