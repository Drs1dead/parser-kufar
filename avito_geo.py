"""Avito RU settlements: static map + text search (preview UI)."""
from __future__ import annotations

import difflib
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent

_GEO_CANDIDATES: tuple[Path, ...] = (
    _ROOT / "geo" / "avito_geo.json",
    _ROOT / "data" / "avito_geo.json",
    Path("/app/data/avito_geo.json"),
)

REGION_SHORTCUTS: dict[str, tuple[str, str, str]] = {
    "москва": ("637640", "637640", "Москва"),
    "санкт-петербург": ("653240", "653240", "Санкт-Петербург"),
    "спб": ("653240", "653240", "Санкт-Петербург"),
    "питер": ("653240", "653240", "Санкт-Петербург"),
    "смоленск": ("653430", "653430", "Смоленск"),
}


@dataclass(frozen=True)
class AvitoGeoPlace:
    label: str
    norm: str
    region_id: str
    city_id: str
    region_label: str


def _norm(text: str) -> str:
    return " ".join(str(text).lower().replace("ё", "е").strip().split())


def resolve_geo_path() -> Path | None:
    for path in _GEO_CANDIDATES:
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=1)
def _load_places() -> tuple[AvitoGeoPlace, ...]:
    path = resolve_geo_path()
    if path is None:
        log.warning(
            "avito geo file missing (checked %s) — only shortcut cities work",
            ", ".join(str(p) for p in _GEO_CANDIDATES),
        )
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.error("avito geo file unreadable %s: %s", path, exc)
        return ()
    out: list[AvitoGeoPlace] = []
    for item in raw:
        label = str(item.get("label") or "").strip()
        city_id = str(item.get("city_id") or "").strip()
        region_id = str(item.get("region_id") or city_id).strip()
        if not label or not city_id:
            continue
        out.append(
            AvitoGeoPlace(
                label=label,
                norm=str(item.get("norm") or _norm(label)),
                region_id=region_id,
                city_id=city_id,
                region_label=str(item.get("region_label") or ""),
            )
        )
    log.info("avito geo loaded %d places from %s", len(out), path)
    return tuple(out)


def _shortcut_place(q: str) -> AvitoGeoPlace | None:
    row = REGION_SHORTCUTS.get(q)
    if not row:
        return None
    region_id, city_id, label = row
    return AvitoGeoPlace(
        label=label,
        norm=q,
        region_id=region_id,
        city_id=city_id,
        region_label=label,
    )


def search_places(query: str, *, limit: int = 5) -> list[AvitoGeoPlace]:
    q = _norm(query)
    if len(q) < 2:
        return []

    shortcut = _shortcut_place(q)
    if shortcut is not None:
        return [shortcut]

    places = _load_places()
    if not places:
        close = difflib.get_close_matches(
            q, list(REGION_SHORTCUTS.keys()), n=limit, cutoff=0.84
        )
        out: list[AvitoGeoPlace] = []
        for name in close:
            place = _shortcut_place(name)
            if place is not None:
                out.append(place)
        return out

    exact = [p for p in places if p.norm == q or _norm(p.label) == q]
    if exact:
        return exact[:limit]

    hits: list[AvitoGeoPlace] = []
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


def place_to_option(place: AvitoGeoPlace) -> dict[str, str]:
    return {
        "label": place.label,
        "region_id": place.region_id,
        "city_id": place.city_id,
    }
