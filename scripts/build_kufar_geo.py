"""One-off: build data/kufar_geo.json from Kufar import documentation."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "kufar_geo.json"
LOCAL_DOC = ROOT / "scripts" / "import_documentation_revision_5.htm"
DOC_URL = "https://import-docs.kufar.by/import_documentation_revision_5.htm"

REGION_RE = re.compile(r"(?:область|город)`region = (\d+)`", re.I)
AREA_RE = re.compile(r"^`(\d+)`(.+)$", re.M)

REGION_LABELS: dict[int, str] = {
    1: "Брестская область",
    2: "Гомельская область",
    3: "Гродненская область",
    4: "Могилевская область",
    5: "Минская область",
    6: "Витебская область",
    7: "Минск",
}


def fetch_doc() -> str:
    if LOCAL_DOC.is_file():
        return LOCAL_DOC.read_text(encoding="utf-8", errors="replace")
    with urllib.request.urlopen(DOC_URL, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_places(text: str) -> list[dict]:
    markers = [(m.start(), int(m.group(1))) for m in REGION_RE.finditer(text)]
    places: list[dict] = []
    for i, (pos, rgn) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else pos + 80_000
        block = text[pos:end]
        region_label = REGION_LABELS.get(rgn, str(rgn))
        for am in AREA_RE.finditer(block):
            ar = int(am.group(1))
            label = am.group(2).strip()
            if not label or len(label) > 80:
                continue
            if label.startswith("region") or "Remuneration" in label:
                continue
            norm = " ".join(label.lower().replace("ё", "е").split())
            places.append(
                {
                    "label": label,
                    "norm": norm,
                    "rgn": rgn,
                    "ar": ar,
                    "region_label": region_label,
                }
            )
    seen: set[tuple[int, int]] = set()
    out: list[dict] = []
    for p in places:
        key = (p["rgn"], p["ar"])
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def main() -> None:
    text = fetch_doc()
    places = parse_places(text)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(places, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written {len(places)} places -> {OUT}")


if __name__ == "__main__":
    main()
