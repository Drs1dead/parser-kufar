"""Каталог фасетов Kufar search-api: модели (phm), память (ppm), города (rgn).

Параметры сняты с GET search-api/v2/search/rendered-paginated (не HTML).
Мультивыбор: phm=v.or:6085,6087 и ppm=v.or:20,25.
query= не используем: это полнотекст, а не фильтр модели.
"""
from __future__ import annotations

import logging
from config import DEFAULT_MEMORY_VOLUMES, MEMORY_VOLUME_OPTIONS
from product_catalog import (
    CAT_LAPTOPS,
    CAT_PHONES,
    CAT_TABLETS,
    CAT_WATCHES,
    is_phones_category,
    normalize_category,
)

log = logging.getLogger(__name__)

KUFAR_PHONE_CAT = 17010
KUFAR_LAPTOP_CAT = 16040
KUFAR_TABLET_CAT = 17050
KUFAR_WATCH_CAT = 17090
KUFAR_PRIVATE_OT = 1
KUFAR_APPLE_LAPTOP_CLB = 5
KUFAR_APPLE_TABLET_PHTBR = 1
KUFAR_IOS_TABLET_PHTO = 5
KUFAR_APPLE_WATCH_PHSWBR = 5
# Apple silicon (без Intel). Снято с search-api computers_laptop_processor.
APPLE_SILICON_CLP: tuple[int, ...] = (
    64,  # M1
    65,  # M2
    66,  # M3
    67,  # M3 Pro
    68,  # M3 Max
    69,  # M4
    71,  # M1 Pro
    73,  # M2 Pro
    75,  # M4 Pro
    76,  # M5
    77,  # M5 Pro
    78,  # M5 Max
)

# Регион API (не район ar). Проверено по полю region.vl в выдаче.
CITY_RGN: dict[str, int] = {
    "minsk": 7,
    "brest": 1,
    "vitebsk": 6,
    "gomel": 2,
    "grodno": 3,
    "mogilev": 4,
}
DEFAULT_CITY = "minsk"
CITY_ORDER: tuple[str, ...] = (
    "minsk",
    "brest",
    "vitebsk",
    "gomel",
    "grodno",
    "mogilev",
)
CITY_LABELS: dict[str, str] = {
    "minsk": "Минск",
    "brest": "Брест",
    "vitebsk": "Витебск",
    "gomel": "Гомель",
    "grodno": "Гродно",
    "mogilev": "Могилёв",
}
# Быстрый выбор «вся область» в UI города (rgn, подпись).
QUICK_RGN_BUTTONS: tuple[tuple[int, str], ...] = (
    (7, CITY_LABELS["minsk"]),
    (1, CITY_LABELS["brest"]),
    (6, CITY_LABELS["vitebsk"]),
    (2, CITY_LABELS["gomel"]),
    (3, CITY_LABELS["grodno"]),
    (4, CITY_LABELS["mogilev"]),
)
RGN_TO_SLUG: dict[int, str] = {v: k for k, v in CITY_RGN.items()}

# 64/128/256/512 ГБ; 512+ = 512 ГБ и «1 ТБ и более».
PPM_BY_MEMORY: dict[str, tuple[int, ...]] = {
    "64": (15,),
    "128": (20,),
    "256": (25,),
    "512": (30,),
    "512+": (30, 35),
}

# Наш DEVICE_CATALOG → phones_model.v (pu=phm). Несколько id — варианты на витрине.
PHM_BY_MODEL: dict[str, tuple[int, ...]] = {
    "iphone se": (235, 6133, 6134, 6135),
    "iphone x": (240,),
    "iphone xs": (250,),
    "iphone xs max": (255,),
    "iphone xr": (245,),
    "iphone 11": (260,),
    "iphone 11 pro": (265,),
    "iphone 11 pro max": (270,),
    "iphone 12": (3740,),
    "iphone 12 mini": (3755,),
    "iphone 12 pro": (3745,),
    "iphone 12 pro max": (3750,),
    "iphone 13": (5380,),
    "iphone 13 mini": (5390,),
    "iphone 13 pro": (5385,),
    "iphone 13 pro max": (5395,),
    "iphone 14": (5625,),
    "iphone 14 plus": (5630,),
    "iphone 14 pro": (5635,),
    "iphone 14 pro max": (5640,),
    "iphone 15": (6085,),
    "iphone 15 plus": (6086,),
    "iphone 15 pro": (6087,),
    "iphone 15 pro max": (6088,),
    "iphone 16": (6145,),
    "iphone 16 plus": (6146,),
    "iphone 16 pro": (6147,),
    "iphone 16 pro max": (6148,),
    "iphone 17": (6178,),
    "iphone 17 pro": (6180,),
    "iphone 17 pro max": (6181,),
    "samsung galaxy s20": (2740,),
    "samsung galaxy s20 plus": (2750,),
    "samsung galaxy s20 ultra": (2745,),
    "samsung galaxy s21": (4480,),
    "samsung galaxy s21 plus": (4490,),
    "samsung galaxy s21 ultra": (4485,),
    "samsung galaxy s22": (5510,),
    "samsung galaxy s22 plus": (5515,),
    "samsung galaxy s22 ultra": (5520,),
    "samsung galaxy s23": (6056,),
    "samsung galaxy s23 plus": (6058,),
    "samsung galaxy s23 ultra": (6057,),
    "samsung galaxy s24": (6106,),
    "samsung galaxy s24 plus": (6107,),
    "samsung galaxy s24 ultra": (6108,),
    "samsung galaxy s25": (6155,),
    "samsung galaxy s25 plus": (6156,),
    "samsung galaxy s25 ultra": (6154,),
    "samsung galaxy z flip": (4500,),
    "samsung galaxy z flip 5g": (4500,),
    "samsung galaxy z flip 3": (5600,),
    "samsung galaxy z flip 4": (5773,),
    "samsung galaxy z flip 5": (6161,),
    "samsung galaxy z flip 6": (6162,),
    # На витрине пока нет отдельного phm — общий «Galaxy Z Flip».
    "samsung galaxy z flip 7": (4500,),
    "samsung galaxy z flip 7 fe": (4500,),
    "samsung galaxy z fold": (2530,),
    "samsung galaxy z fold 2": (4510,),
    "samsung galaxy z fold 3": (5605,),
    "samsung galaxy z fold 4": (5774,),
    "samsung galaxy z fold 5": (6105,),
    "samsung galaxy z fold 6": (6160,),
    "samsung galaxy z fold 7": (6267,),
}


def _norm_token(value: str) -> str:
    return " ".join(str(value).lower().replace("ё", "е").split())


def or_facet(ids: list[int] | tuple[int, ...]) -> str:
    """Kufar multi-value: v.or:20,25."""
    uniq: list[str] = []
    seen: set[str] = set()
    for raw in ids:
        token = str(int(raw))
        if token in seen:
            continue
        seen.add(token)
        uniq.append(token)
    if not uniq:
        return ""
    return "v.or:" + ",".join(uniq)


def normalize_city(city: str | None) -> str:
    key = _norm_token(city or "") or DEFAULT_CITY
    return key if key in CITY_RGN else DEFAULT_CITY


def city_label(city: str | None) -> str:
    return CITY_LABELS.get(normalize_city(city), CITY_LABELS[DEFAULT_CITY])


def user_city_label(user: dict | None) -> str:
    if not user:
        return CITY_LABELS[DEFAULT_CITY]
    custom = (user.get("city_label") or "").strip()
    if custom:
        return custom
    return city_label(user.get("city"))


def user_rgn(user: dict | None) -> int:
    if user and user.get("city_rgn") is not None:
        return int(user["city_rgn"])
    return city_rgn((user or {}).get("city"))


def user_ar(user: dict | None) -> int | None:
    if not user:
        return None
    ar = user.get("city_ar")
    if ar is None:
        return None
    return int(ar)


def city_rgn(city: str | None) -> int:
    return CITY_RGN[normalize_city(city)]


def _memory_ppm_ids(memories: list[str] | tuple[str, ...]) -> list[int]:
    allowed = set(MEMORY_VOLUME_OPTIONS)
    ids: list[int] = []
    for raw in memories:
        token = str(raw).strip()
        if token not in allowed:
            continue
        ids.extend(PPM_BY_MEMORY.get(token, ()))
    return ids


def _split_models(models: list[str] | tuple[str, ...]) -> tuple[list[int], list[str]]:
    phm: list[int] = []
    missing: list[str] = []
    seen_phm: set[int] = set()
    for raw in models:
        key = _norm_token(raw)
        if not key:
            continue
        mapped = PHM_BY_MODEL.get(key)
        if not mapped:
            missing.append(key)
            continue
        for item in mapped:
            if item not in seen_phm:
                seen_phm.add(item)
                phm.append(item)
    return phm, missing


def catalog_search_params(
    rgn: int,
    ar: int | None,
    models: list[str] | tuple[str, ...],
    memories: list[str] | tuple[str, ...],
    *,
    category: str | None = None,
) -> list[dict[str, str]]:
    """Facet-параметры для search-api. Без query: на Kufar это полнотекст, не фильтр модели."""
    kind = normalize_category(category)
    rgn_str = str(int(rgn))
    if kind == CAT_PHONES:
        return _phone_search_params(rgn_str, ar, models, memories)
    if kind == CAT_LAPTOPS:
        return _laptop_search_params(rgn_str, ar, models)
    if kind == CAT_TABLETS:
        return _tablet_search_params(rgn_str, ar, models)
    if kind == CAT_WATCHES:
        return _watch_search_params(rgn_str, ar, models)
    return []


def _apply_ar(row: dict[str, str], ar: int | None) -> dict[str, str]:
    if ar is not None:
        row["ar"] = str(int(ar))
    return row


def _phone_search_params(
    rgn: str,
    ar: int | None,
    models: list[str] | tuple[str, ...],
    memories: list[str] | tuple[str, ...],
) -> list[dict[str, str]]:
    ppm = or_facet(_memory_ppm_ids(memories))
    phm_ids, missing = _split_models(models)
    for name in missing:
        log.warning("kufar catalog: no phm for model %r, skip", name)
    if not phm_ids:
        return []
    row: dict[str, str] = {
        "cat": str(KUFAR_PHONE_CAT),
        "ot": str(KUFAR_PRIVATE_OT),
        "rgn": rgn,
        "phm": or_facet(phm_ids),
    }
    if ppm:
        row["ppm"] = ppm
    return [_apply_ar(row, ar)]


def _laptop_search_params(
    rgn: str,
    ar: int | None,
    models: list[str] | tuple[str, ...],
) -> list[dict[str, str]]:
    if not any(_norm_token(m).startswith("macbook") for m in models):
        return []
    clp = or_facet(APPLE_SILICON_CLP)
    row: dict[str, str] = {
        "cat": str(KUFAR_LAPTOP_CAT),
        "ot": str(KUFAR_PRIVATE_OT),
        "rgn": rgn,
        "clb": str(KUFAR_APPLE_LAPTOP_CLB),
    }
    if clp:
        row["clp"] = clp
    return [_apply_ar(row, ar)]


def _tablet_search_params(
    rgn: str,
    ar: int | None,
    models: list[str] | tuple[str, ...],
) -> list[dict[str, str]]:
    if not any(_norm_token(m).startswith("ipad") for m in models):
        return []
    return [
        _apply_ar(
            {
                "cat": str(KUFAR_TABLET_CAT),
                "ot": str(KUFAR_PRIVATE_OT),
                "rgn": rgn,
                "phtbr": str(KUFAR_APPLE_TABLET_PHTBR),
                "phto": str(KUFAR_IOS_TABLET_PHTO),
            },
            ar,
        )
    ]


def _watch_search_params(
    rgn: str,
    ar: int | None,
    models: list[str] | tuple[str, ...],
) -> list[dict[str, str]]:
    if not any(_norm_token(m).startswith("apple watch") for m in models):
        return []
    return [
        _apply_ar(
            {
                "cat": str(KUFAR_WATCH_CAT),
                "ot": str(KUFAR_PRIVATE_OT),
                "rgn": rgn,
                "phswbr": str(KUFAR_APPLE_WATCH_PHSWBR),
            },
            ar,
        )
    ]


from marketplace.keys import FetchKey, fetch_key_for_user, group_users_by_fetch_key
