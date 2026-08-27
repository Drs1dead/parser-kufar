"""Kufar BY settlements: static map + text search for city picker."""
from __future__ import annotations

import difflib
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

GEO_PATH = Path(__file__).resolve().parent / "data" / "kufar_geo.json"

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


def geo_data_available() -> bool:
    return GEO_PATH.is_file()


@lru_cache(maxsize=1)
def _load_places() -> tuple[GeoPlace, ...]:
    if not GEO_PATH.is_file():
        log.error("kufar geo file missing: %s", GEO_PATH)
        return ()
    raw = json.loads(GEO_PATH.read_text(encoding="utf-8"))
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
    """Точное совпадение → алиасы → substring → fuzzy."""
    q = _norm(query)
    if len(q) < 2:
        return []

    shortcut = _shortcut_place(q)
    if shortcut is not None:
        return [shortcut]

    places = _load_places()
    if not places:
        return []

    exact = [p for p in places if p.norm == q or _norm(p.label) == q]
    if exact:
        return exact[:limit]

    hits: list[GeoPlace] = []
    for place in places:
        if q in place.norm or q in _norm(place.label):
            hits.append(place)
    if hits:
        hits.sort(key=lambda p: (p.norm != q, p.norm.startswith(q) is False, len(p.norm)))
        return hits[:limit]

    close = difflib.get_close_matches(q, [p.norm for p in places], n=limit, cutoff=0.75)
    out: list[GeoPlace] = []
    for name in close:
        for place in places:
            if place.norm == name:
                out.append(place)
                break
    return out
