"""Fetch-ключи рассылки: source + категория + geo + модели + память."""
from __future__ import annotations

from collections import defaultdict

from config import AVITO_ENABLED, DEFAULT_MEMORY_VOLUMES, MEMORY_VOLUME_OPTIONS
from kufar_catalog import _norm_token, user_ar, user_rgn
from marketplace.types import (
    COUNTRY_BY,
    COUNTRY_RU,
    SOURCE_AVITO,
    SOURCE_KUFAR,
    normalize_country,
    normalize_primary_source,
)
from product_catalog import DEFAULT_CATEGORY, is_phones_category, normalize_category

# geo: для Kufar — str(rgn), str(ar); для Avito — region_id, city_id
FetchKey = tuple[str, str, str, str, tuple[str, ...], tuple[str, ...]]


def user_primary_source(user: dict | None) -> str:
    return normalize_primary_source((user or {}).get("primary_source"))


def user_is_kufar_pollable(user: dict | None) -> bool:
    if not user:
        return False
    country = normalize_country(user.get("country"))
    return country == COUNTRY_BY and user_primary_source(user) == SOURCE_KUFAR


def user_is_avito_pollable(user: dict | None) -> bool:
    if not AVITO_ENABLED or not user:
        return False
    country = normalize_country(user.get("country"))
    if country != COUNTRY_RU or user_primary_source(user) != SOURCE_AVITO:
        return False
    city_id = str(user.get("avito_city_id") or "").strip()
    return bool(city_id)


def _kufar_geo_key(user: dict | None) -> tuple[str, str]:
    rgn = user_rgn(user)
    ar = user_ar(user)
    return str(rgn), str(ar) if ar is not None else ""


def _avito_geo_key(user: dict | None) -> tuple[str, str]:
    region_id = str((user or {}).get("avito_region_id") or "").strip()
    city_id = str((user or {}).get("avito_city_id") or "").strip()
    return region_id, city_id


def fetch_key_for_user(user: dict | None) -> FetchKey:
    source = user_primary_source(user)
    category = normalize_category((user or {}).get("product_category"))
    models = tuple(
        sorted(
            {
                _norm_token(k)
                for k in (user or {}).get("keywords") or []
                if str(k).strip()
            }
        )
    )
    if source == SOURCE_AVITO:
        geo_a, geo_b = _avito_geo_key(user)
    else:
        geo_a, geo_b = _kufar_geo_key(user)
    if not is_phones_category(category):
        return (source, category, geo_a, geo_b, models, ())
    raw_mem = (user or {}).get("memory_volumes") or list(DEFAULT_MEMORY_VOLUMES)
    allowed = set(MEMORY_VOLUME_OPTIONS)
    memories = tuple(
        sorted(str(v).strip() for v in raw_mem if str(v).strip() in allowed)
    )
    if not memories:
        memories = tuple(DEFAULT_MEMORY_VOLUMES)
    return (source, category, geo_a, geo_b, models, memories)


def group_users_by_fetch_key(users: list[dict]) -> dict[FetchKey, list[dict]]:
    groups: dict[FetchKey, list[dict]] = defaultdict(list)
    for user in users:
        source = user_primary_source(user)
        if source == SOURCE_KUFAR and not user_is_kufar_pollable(user):
            continue
        if source == SOURCE_AVITO and not user_is_avito_pollable(user):
            continue
        key = fetch_key_for_user(user)
        if not key[4]:
            continue
        groups[key].append(user)
    return dict(groups)
