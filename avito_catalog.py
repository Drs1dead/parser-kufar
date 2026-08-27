"""Query params для Avito collector search API (Фаза 4.2).

Аналог catalog_search_params на Kufar: FetchKey → GET query для backend.
"""
from __future__ import annotations

from product_catalog import is_phones_category, normalize_category

_SOURCE_AVITO = "avito"

FetchKey = tuple[str, str, str, str, tuple[str, ...], tuple[str, ...]]


def search_params_from_key(key: FetchKey) -> dict[str, str] | None:
    source, category, geo_a, geo_b, models, memories = key
    if source != _SOURCE_AVITO or not models:
        return None
    city_id = str(geo_b or geo_a or "").strip()
    if not city_id:
        return None
    cat = normalize_category(category)
    params: dict[str, str] = {
        "city_id": city_id,
        "category": cat,
        "models": ",".join(models),
    }
    region_id = str(geo_a or "").strip()
    if region_id:
        params["region_id"] = region_id
    if is_phones_category(cat) and memories:
        params["memory_gb"] = ",".join(memories)
    return params
