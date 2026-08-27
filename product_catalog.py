"""Категории товаров бота: одна активная на пользователя.

Смартфоны — Apple и Samsung (как раньше).
Ноутбуки / планшеты / часы — только Apple, примерно с 2020.
"""
from __future__ import annotations

CAT_PHONES = "phones"
CAT_LAPTOPS = "laptops"
CAT_TABLETS = "tablets"
CAT_WATCHES = "watches"
DEFAULT_CATEGORY = CAT_PHONES
PRODUCT_CATEGORIES: tuple[str, ...] = (
    CAT_PHONES,
    CAT_LAPTOPS,
    CAT_TABLETS,
    CAT_WATCHES,
)
CATEGORY_LABELS: dict[str, str] = {
    CAT_PHONES: "Смартфоны",
    CAT_LAPTOPS: "Ноутбуки",
    CAT_TABLETS: "Планшеты",
    CAT_WATCHES: "Смарт-часы",
}
CATEGORY_EMOJI: dict[str, str] = {
    CAT_PHONES: "📱",
    CAT_LAPTOPS: "💻",
    CAT_TABLETS: "📲",
    CAT_WATCHES: "⌚",
}

PHONE_MODELS: tuple[str, ...] = (
    "iphone se",
    "iphone x",
    "iphone xs",
    "iphone xs max",
    "iphone xr",
    "iphone 11",
    "iphone 11 pro",
    "iphone 11 pro max",
    "iphone 12",
    "iphone 12 mini",
    "iphone 12 pro",
    "iphone 12 pro max",
    "iphone 13",
    "iphone 13 mini",
    "iphone 13 pro",
    "iphone 13 pro max",
    "iphone 14",
    "iphone 14 plus",
    "iphone 14 pro",
    "iphone 14 pro max",
    "iphone 15",
    "iphone 15 plus",
    "iphone 15 pro",
    "iphone 15 pro max",
    "iphone 16",
    "iphone 16 plus",
    "iphone 16 pro",
    "iphone 16 pro max",
    "iphone 17",
    "iphone 17 pro",
    "iphone 17 pro max",
    "samsung galaxy s20",
    "samsung galaxy s20 plus",
    "samsung galaxy s20 ultra",
    "samsung galaxy s21",
    "samsung galaxy s21 plus",
    "samsung galaxy s21 ultra",
    "samsung galaxy s22",
    "samsung galaxy s22 plus",
    "samsung galaxy s22 ultra",
    "samsung galaxy s23",
    "samsung galaxy s23 plus",
    "samsung galaxy s23 ultra",
    "samsung galaxy s24",
    "samsung galaxy s24 plus",
    "samsung galaxy s24 ultra",
    "samsung galaxy s25",
    "samsung galaxy s25 plus",
    "samsung galaxy s25 ultra",
    "samsung galaxy z flip",
    "samsung galaxy z flip 5g",
    "samsung galaxy z flip 3",
    "samsung galaxy z flip 4",
    "samsung galaxy z flip 5",
    "samsung galaxy z flip 6",
    "samsung galaxy z flip 7",
    "samsung galaxy z flip 7 fe",
    "samsung galaxy z fold",
    "samsung galaxy z fold 2",
    "samsung galaxy z fold 3",
    "samsung galaxy z fold 4",
    "samsung galaxy z fold 5",
    "samsung galaxy z fold 6",
    "samsung galaxy z fold 7",
)

# Apple silicon с M1 (2020). Intel 2019 в каталог не кладём.
LAPTOP_MODELS: tuple[str, ...] = (
    "macbook air m1",
    "macbook air m2",
    "macbook air m3",
    "macbook air m4",
    "macbook air m5",
    "macbook pro 13 m1",
    "macbook pro 14",
    "macbook pro 16",
)

TABLET_MODELS: tuple[str, ...] = (
    "ipad 8",
    "ipad 9",
    "ipad 10",
    "ipad 11",
    "ipad air 4",
    "ipad air 5",
    "ipad air m2",
    "ipad air m3",
    "ipad mini 6",
    "ipad mini 7",
    "ipad pro 11",
    "ipad pro 12.9",
    "ipad pro 13",
)

WATCH_MODELS: tuple[str, ...] = (
    "apple watch series 6",
    "apple watch series 7",
    "apple watch series 8",
    "apple watch series 9",
    "apple watch series 10",
    "apple watch series 11",
    "apple watch se",
    "apple watch se 2",
    "apple watch se 3",
    "apple watch ultra",
    "apple watch ultra 2",
)

DEVICE_CATALOG: tuple[str, ...] = (
    PHONE_MODELS + LAPTOP_MODELS + TABLET_MODELS + WATCH_MODELS
)
DEVICE_CATALOG_SET: frozenset[str] = frozenset(DEVICE_CATALOG)

# Новые пользователи выбирают модели сами.
DEFAULT_KEYWORDS: tuple[str, ...] = ()


def normalize_category(value: str | None) -> str:
    key = " ".join(str(value or "").lower().split())
    return key if key in CATEGORY_LABELS else DEFAULT_CATEGORY


def category_label(value: str | None) -> str:
    return CATEGORY_LABELS[normalize_category(value)]


def is_phones_category(value: str | None) -> bool:
    return normalize_category(value) == CAT_PHONES


_MODEL_PREFIXES: tuple[tuple[str, str], ...] = (
    ("samsung galaxy z flip", "Galaxy Z Flip"),
    ("samsung galaxy z fold", "Galaxy Z Fold"),
    ("samsung galaxy", "Galaxy"),
    ("apple watch", "Apple Watch"),
    ("macbook", "MacBook"),
    ("ipad", "iPad"),
    ("iphone", "iPhone"),
)

_MODEL_TOKEN_LABELS: dict[str, str] = {
    "se": "SE",
    "xs": "XS",
    "xr": "XR",
    "pro": "Pro",
    "max": "Max",
    "plus": "Plus",
    "mini": "mini",
    "ultra": "Ultra",
    "air": "Air",
    "fe": "FE",
    "5g": "5G",
    "series": "Series",
}


def _token_label(token: str) -> str:
    mapped = _MODEL_TOKEN_LABELS.get(token)
    if mapped:
        return mapped
    if len(token) >= 2 and token[0] == "m" and token[1:].isdigit():
        return token.upper()
    return token.upper() if token.isalpha() and len(token) <= 2 else token.capitalize()


def model_label(raw: str) -> str:
    """Подпись модели для UI. Ключ в БД не меняем."""
    key = " ".join(str(raw or "").lower().split())
    if not key:
        return ""
    title = None
    rest = key
    for prefix, pretty in _MODEL_PREFIXES:
        if key == prefix or key.startswith(prefix + " "):
            title = pretty
            rest = key[len(prefix) :].strip()
            break
    if title is None:
        return key
    if not rest:
        return title
    return f"{title} {' '.join(_token_label(tok) for tok in rest.split())}"
