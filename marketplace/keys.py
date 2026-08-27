"""Fetch-ключи рассылки: source + категория + geo + модели + память."""
from __future__ import annotations

from collections import defaultdict

from config import DEFAULT_MEMORY_VOLUMES, MEMORY_VOLUME_OPTIONS
from kufar_catalog import _norm_token, user_ar, user_rgn
from marketplace.types import COUNTRY_BY, SOURCE_KUFAR, normalize_primary_source
from product_catalog import DEFAULT_CATEGORY, is_phones_category, normalize_category

FetchKey = tuple[str, str, int, int | None, tuple[str, ...], tuple[str, ...]]


def user_primary_source(user: dict | None) -> str:
    return normalize_primary_source((user or {}).get("primary_source"))


def user_is_pollable(user: dict | None) -> bool:
    """Сейчас poll только Беларусь + Kufar."""
    if not user:
        return False
    country = str(user.get("country") or COUNTRY_BY).strip().lower()
    return country == COUNTRY_BY and user_primary_source(user) == SOURCE_KUFAR


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
    if not is_phones_category(category):
        return (source, category, user_rgn(user), user_ar(user), models, ())
    raw_mem = (user or {}).get("memory_volumes") or list(DEFAULT_MEMORY_VOLUMES)
    allowed = set(MEMORY_VOLUME_OPTIONS)
    memories = tuple(
        sorted(str(v).strip() for v in raw_mem if str(v).strip() in allowed)
    )
    if not memories:
        memories = tuple(DEFAULT_MEMORY_VOLUMES)
    return (source, category, user_rgn(user), user_ar(user), models, memories)


def group_users_by_fetch_key(users: list[dict]) -> dict[FetchKey, list[dict]]:
    groups: dict[FetchKey, list[dict]] = defaultdict(list)
    for user in users:
        if not user_is_pollable(user):
            continue
        key = fetch_key_for_user(user)
        if not key[4]:
            continue
        groups[key].append(user)
    return dict(groups)
