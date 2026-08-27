"""Kufar BY settlements: static map + text search for city picker."""
from __future__ import annotations

import difflib
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent

# geo/ — в git и на деплое; data/ — legacy и ручная копия на BotHost.
_GEO_CANDIDATES: tuple[Path, ...] = (
    _ROOT / "geo" / "kufar_geo.json",
    _ROOT / "data" / "kufar_geo.json",
    Path("/app/data/kufar_geo.json"),
)

# Точные алиасы: вся область (ar=None) или конкретный НП.
REGION_SHORTCUTS: dict[str, tuple[int, int | None, str]] = {
    "минск": (7, None, "Минск"),
    "брест": (1, None, "Брест"),
    "витебск": (6, None, "Витебск"),
    "гомель": (2, None, "Гомель"),
    "гродно": (3, None, "Гродно"),
    "могилев": (4, None, "Могилёв"),
    "могилёв": (4, None, "Могилёв"),
    "бобруйск": (4, 12, "Бобруйск"),
    "барановичи": (1, 37, "Барановичи"),
    "пинск": (1, 4, "Пинск"),
    "борисов": (5, 15, "Борисов"),
    "молодечно": (5, 16, "Молодечно"),
    "орша": (6, 19, "Орша"),
    "полоцк": (6, 20, "Полоцк"),
    "солигорск": (5, 45, "Солигорск"),
    "жодино": (5, 44, "Жодино"),
    "слуцк": (5, 17, "Слуцк"),
    "новополоцк": (6, 46, "Новополоцк"),
}

REGION_LABEL_BY_RGN: dict[int, str] = {
    1: "Брестская область",
    2: "Гомельская область",
    3: "Гродненская область",
    4: "Могилевская область",
    5: "Минская область",
    6: "Витебская область",
    7: "Минск",
}


@dataclass(frozen=True)
class GeoPlace:
    label: str
    norm: str
    rgn: int
    ar: int | None
    region_label: str


def _norm(text: str) -> str:
    return " ".join(str(text).lower().replace("ё", "е").strip().split())


def resolve_geo_path() -> Path | None:
    for path in _GEO_CANDIDATES:
        if path.is_file():
            return path
    return None


def geo_data_available() -> bool:
    return resolve_geo_path() is not None


@lru_cache(maxsize=1)
def _load_places() -> tuple[GeoPlace, ...]:
    path = resolve_geo_path()
    if path is None:
        log.warning(
            "kufar geo file missing (checked %s) — only shortcut cities work",
            ", ".join(str(p) for p in _GEO_CANDIDATES),
        )
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.error("kufar geo file unreadable %s: %s", path, exc)
        return ()
    out: list[GeoPlace] = []
    for item in raw:
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        ar_raw = item.get("ar")
        ar_val = int(ar_raw) if ar_raw is not None else None
        out.append(
            GeoPlace(
                label=label,
                norm=str(item.get("norm") or _norm(label)),
                rgn=int(item["rgn"]),
                ar=ar_val,
                region_label=str(item.get("region_label") or ""),
            )
        )
    log.info("kufar geo loaded %d places from %s", len(out), path)
    return tuple(out)


def _shortcut_place(q: str) -> GeoPlace | None:
    row = REGION_SHORTCUTS.get(q)
    if not row:
        return None
    rgn, ar, label = row
    return GeoPlace(
        label=label,
        norm=q,
        rgn=rgn,
        ar=ar,
        region_label=REGION_LABEL_BY_RGN.get(rgn, ""),
    )


def search_places(query: str, *, limit: int = 5) -> list[GeoPlace]:
    """Точное совпадение → алиасы → каталог JSON → fuzzy."""
    q = _norm(query)
    if len(q) < 2:
        return []

    shortcut = _shortcut_place(q)
    if shortcut is not None:
        return [shortcut]

    places = _load_places()
    if not places:
        # Fuzzy по встроенным алиасам, если JSON недоступен.
        close = difflib.get_close_matches(
            q, list(REGION_SHORTCUTS.keys()), n=limit, cutoff=0.84
        )
        out: list[GeoPlace] = []
        for name in close:
            place = _shortcut_place(name)
            if place is not None:
                out.append(place)
        return out

    exact = [p for p in places if p.norm == q or _norm(p.label) == q]
    if exact:
        return exact[:limit]

    hits: list[GeoPlace] = []
    for place in places:
        if q in place.norm or q in _norm(place.label):
            hits.append(place)
    if hits:
        hits.sort(key=lambda p: (p.norm != q, not p.norm.startswith(q), len(p.norm)))
        return hits[:limit]

    close = difflib.get_close_matches(q, [p.norm for p in places], n=limit, cutoff=0.75)
    out = []
    for name in close:
        for place in places:
            if place.norm == name:
                out.append(place)
                break
    return out
