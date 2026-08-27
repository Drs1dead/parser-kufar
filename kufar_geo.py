"""Kufar BY settlements: static map + text search for city picker."""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

GEO_PATH = Path(__file__).resolve().parent / "data" / "kufar_geo.json"


@dataclass(frozen=True)
class GeoPlace:
    label: str
    norm: str
    rgn: int
    ar: int
    region_label: str


def _norm(text: str) -> str:
    return " ".join(str(text).lower().replace("ё", "е").strip().split())


@lru_cache(maxsize=1)
def _load_places() -> tuple[GeoPlace, ...]:
    raw = json.loads(GEO_PATH.read_text(encoding="utf-8"))
    out: list[GeoPlace] = []
    for item in raw:
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        out.append(
            GeoPlace(
                label=label,
                norm=str(item.get("norm") or _norm(label)),
                rgn=int(item["rgn"]),
                ar=int(item["ar"]),
                region_label=str(item.get("region_label") or ""),
            )
        )
    return tuple(out)


def search_places(query: str, *, limit: int = 5) -> list[GeoPlace]:
    """Substring match first; optional fuzzy fallback via difflib."""
    q = _norm(query)
    if len(q) < 2:
        return []
    places = _load_places()
    hits: list[GeoPlace] = []
    for place in places:
        if q in place.norm or q in _norm(place.label):
            hits.append(place)
    if hits:
        return hits[:limit]
    close = difflib.get_close_matches(q, [p.norm for p in places], n=limit, cutoff=0.6)
    out: list[GeoPlace] = []
    for name in close:
        for place in places:
            if place.norm == name:
                out.append(place)
                break
    return out
