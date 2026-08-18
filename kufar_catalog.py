"""Каталог фасетов Kufar search-api: модели (phm), память (ppm), города (rgn).

Параметры сняты с GET search-api/v2/search/rendered-paginated (не HTML).
Мультивыбор: phm=v.or:6085,6087 и ppm=v.or:20,25.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from config import DEFAULT_MEMORY_VOLUMES, MEMORY_VOLUME_OPTIONS

log = logging.getLogger(__name__)

KUFAR_PHONE_CAT = 17010
KUFAR_PRIVATE_OT = 1

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
    city: str,
    models: list[str] | tuple[str, ...],
    memories: list[str] | tuple[str, ...],
) -> list[dict[str, str]]:
    """Facet-параметры для search-api. Несколько dict — если есть fallback query."""
    rgn = str(city_rgn(city))
    ppm = or_facet(_memory_ppm_ids(memories))
    phm_ids, missing = _split_models(models)
    for name in missing:
        log.warning("kufar catalog: no phm for model %r, fallback query", name)

    base: dict[str, str] = {
        "cat": str(KUFAR_PHONE_CAT),
        "ot": str(KUFAR_PRIVATE_OT),
        "rgn": rgn,
    }
    if ppm:
        base["ppm"] = ppm

    out: list[dict[str, str]] = []
    if phm_ids:
        row = dict(base)
        row["phm"] = or_facet(phm_ids)
        out.append(row)
    for name in missing:
        row = dict(base)
        row["query"] = name
        out.append(row)
    return out


FetchKey = tuple[str, tuple[str, ...], tuple[str, ...]]


def fetch_key_for_user(user: dict | None) -> FetchKey:
    """Ключ выдачи: город + модели + память."""
    models = tuple(
        sorted(
            {
                _norm_token(k)
                for k in (user or {}).get("keywords") or []
                if str(k).strip()
            }
        )
    )
    raw_mem = (user or {}).get("memory_volumes") or list(DEFAULT_MEMORY_VOLUMES)
    allowed = set(MEMORY_VOLUME_OPTIONS)
    memories = tuple(
        sorted(str(v).strip() for v in raw_mem if str(v).strip() in allowed)
    )
    if not memories:
        memories = tuple(DEFAULT_MEMORY_VOLUMES)
    return (normalize_city((user or {}).get("city")), models, memories)


def group_users_by_fetch_key(users: list[dict]) -> dict[FetchKey, list[dict]]:
    groups: dict[FetchKey, list[dict]] = defaultdict(list)
    for user in users:
        key = fetch_key_for_user(user)
        if not key[1]:
            continue
        groups[key].append(user)
    return dict(groups)
