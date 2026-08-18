"""Дерево «Товары»: линейки по категориям."""
from __future__ import annotations

from product_catalog import (
    LAPTOP_MODELS,
    PHONE_MODELS,
    TABLET_MODELS,
    WATCH_MODELS,
)

# Короткие slug для callback (Telegram лимит 64 байта на callback_data)
LINE_BASIC = "b"
LINE_PRO = "p"
LINE_MAX = "m"
SAMSUNG_SERIES_S = "s"
SAMSUNG_SERIES_FLIP = "f"
SAMSUNG_SERIES_FOLD = "d"
SAMSUNG_LINE_BASE = "b"
SAMSUNG_LINE_PLUS = "p"
SAMSUNG_LINE_ULTRA = "u"
SAMSUNG_LINE_FLIP = "f"
SAMSUNG_LINE_FOLD = "d"
LAPTOP_LINE_AIR = "a"
LAPTOP_LINE_PRO = "p"
TABLET_LINE_IPAD = "i"
TABLET_LINE_AIR = "a"
TABLET_LINE_MINI = "n"
TABLET_LINE_PRO = "p"
WATCH_LINE_SERIES = "s"
WATCH_LINE_SE = "e"
WATCH_LINE_ULTRA = "u"

LINE_LABELS: dict[str, str] = {
    LINE_BASIC: "iPhone / mini / Plus / SE",
    LINE_PRO: "iPhone Pro",
    LINE_MAX: "iPhone Pro Max",
}

SAMSUNG_SERIES_LABELS: dict[str, str] = {
    SAMSUNG_SERIES_S: "Galaxy S",
    SAMSUNG_SERIES_FLIP: "Galaxy Z Flip",
    SAMSUNG_SERIES_FOLD: "Galaxy Z Fold",
}

SAMSUNG_LINE_LABELS: dict[str, str] = {
    SAMSUNG_LINE_BASE: "Galaxy S",
    SAMSUNG_LINE_PLUS: "Galaxy S+",
    SAMSUNG_LINE_ULTRA: "Galaxy S Ultra",
    SAMSUNG_LINE_FLIP: "Galaxy Z Flip",
    SAMSUNG_LINE_FOLD: "Galaxy Z Fold",
}

SAMSUNG_SERIES_LINES: dict[str, tuple[str, ...]] = {
    SAMSUNG_SERIES_S: (SAMSUNG_LINE_BASE, SAMSUNG_LINE_PLUS, SAMSUNG_LINE_ULTRA),
    SAMSUNG_SERIES_FLIP: (SAMSUNG_LINE_FLIP,),
    SAMSUNG_SERIES_FOLD: (SAMSUNG_LINE_FOLD,),
}

LAPTOP_LINE_LABELS: dict[str, str] = {
    LAPTOP_LINE_AIR: "MacBook Air",
    LAPTOP_LINE_PRO: "MacBook Pro",
}
TABLET_LINE_LABELS: dict[str, str] = {
    TABLET_LINE_IPAD: "iPad",
    TABLET_LINE_AIR: "iPad Air",
    TABLET_LINE_MINI: "iPad mini",
    TABLET_LINE_PRO: "iPad Pro",
}
WATCH_LINE_LABELS: dict[str, str] = {
    WATCH_LINE_SERIES: "Series",
    WATCH_LINE_SE: "SE",
    WATCH_LINE_ULTRA: "Ultra",
}

GOODS_PER_PAGE = 8


def line_slug_for_catalog_entry(device: str) -> str:
    """Отнести строку каталога к линейке: Pro Max, Pro (не Max), остальное — базовая линейка."""
    s = " ".join((device or "").lower().split())
    if "pro max" in s:
        return LINE_MAX
    parts = s.split()
    if parts and parts[-1] == "pro":
        return LINE_PRO
    return LINE_BASIC


def apple_lines_map() -> dict[str, tuple[str, ...]]:
    """iPhone из каталога смартфонов, сгруппированные по линейке."""
    buckets: dict[str, list[str]] = {LINE_BASIC: [], LINE_PRO: [], LINE_MAX: []}
    for d in PHONE_MODELS:
        if not d.lower().startswith("iphone"):
            continue
        buckets[line_slug_for_catalog_entry(d)].append(d)
    return {k: tuple(v) for k, v in buckets.items()}


def samsung_line_slug_for_catalog_entry(device: str) -> str | None:
    s = " ".join((device or "").lower().split())
    if s.startswith("samsung galaxy z flip"):
        return SAMSUNG_LINE_FLIP
    if s.startswith("samsung galaxy z fold"):
        return SAMSUNG_LINE_FOLD
    if not s.startswith("samsung galaxy s"):
        return None
    if " ultra" in s:
        return SAMSUNG_LINE_ULTRA
    if " plus" in s:
        return SAMSUNG_LINE_PLUS
    return SAMSUNG_LINE_BASE


def samsung_lines_map() -> dict[str, tuple[str, ...]]:
    buckets: dict[str, list[str]] = {
        SAMSUNG_LINE_BASE: [],
        SAMSUNG_LINE_PLUS: [],
        SAMSUNG_LINE_ULTRA: [],
        SAMSUNG_LINE_FLIP: [],
        SAMSUNG_LINE_FOLD: [],
    }
    for d in PHONE_MODELS:
        slug = samsung_line_slug_for_catalog_entry(d)
        if slug is not None:
            buckets[slug].append(d)
    return {k: tuple(v) for k, v in buckets.items()}


def laptop_line_slug_for_catalog_entry(device: str) -> str | None:
    s = " ".join((device or "").lower().split())
    if s.startswith("macbook air"):
        return LAPTOP_LINE_AIR
    if s.startswith("macbook pro"):
        return LAPTOP_LINE_PRO
    return None


def laptop_lines_map() -> dict[str, tuple[str, ...]]:
    buckets: dict[str, list[str]] = {LAPTOP_LINE_AIR: [], LAPTOP_LINE_PRO: []}
    for d in LAPTOP_MODELS:
        slug = laptop_line_slug_for_catalog_entry(d)
        if slug is not None:
            buckets[slug].append(d)
    return {k: tuple(v) for k, v in buckets.items()}


def tablet_line_slug_for_catalog_entry(device: str) -> str | None:
    s = " ".join((device or "").lower().split())
    if not s.startswith("ipad"):
        return None
    if s.startswith("ipad air"):
        return TABLET_LINE_AIR
    if s.startswith("ipad mini"):
        return TABLET_LINE_MINI
    if s.startswith("ipad pro"):
        return TABLET_LINE_PRO
    return TABLET_LINE_IPAD


def tablet_lines_map() -> dict[str, tuple[str, ...]]:
    buckets: dict[str, list[str]] = {
        TABLET_LINE_IPAD: [],
        TABLET_LINE_AIR: [],
        TABLET_LINE_MINI: [],
        TABLET_LINE_PRO: [],
    }
    for d in TABLET_MODELS:
        slug = tablet_line_slug_for_catalog_entry(d)
        if slug is not None:
            buckets[slug].append(d)
    return {k: tuple(v) for k, v in buckets.items()}


def watch_line_slug_for_catalog_entry(device: str) -> str | None:
    s = " ".join((device or "").lower().split())
    if not s.startswith("apple watch"):
        return None
    if s.startswith("apple watch ultra"):
        return WATCH_LINE_ULTRA
    if s.startswith("apple watch se"):
        return WATCH_LINE_SE
    return WATCH_LINE_SERIES


def watch_lines_map() -> dict[str, tuple[str, ...]]:
    buckets: dict[str, list[str]] = {
        WATCH_LINE_SERIES: [],
        WATCH_LINE_SE: [],
        WATCH_LINE_ULTRA: [],
    }
    for d in WATCH_MODELS:
        slug = watch_line_slug_for_catalog_entry(d)
        if slug is not None:
            buckets[slug].append(d)
    return {k: tuple(v) for k, v in buckets.items()}


APPLE_LINES: dict[str, tuple[str, ...]] = apple_lines_map()
SAMSUNG_LINES: dict[str, tuple[str, ...]] = samsung_lines_map()
LAPTOP_LINES: dict[str, tuple[str, ...]] = laptop_lines_map()
TABLET_LINES: dict[str, tuple[str, ...]] = tablet_lines_map()
WATCH_LINES: dict[str, tuple[str, ...]] = watch_lines_map()
