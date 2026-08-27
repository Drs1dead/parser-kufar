"""Анти-мусор для объявлений Avito (RU)."""
from __future__ import annotations

from filters import REJECT_THIN_JUNK, _contains_stem, normalize

AVITO_THIN_JUNK_STEMS: tuple[str, ...] = (
    "копия",
    "копи",
    "реплик",
    "дубликат",
    "запчаст",
    "разбор",
    "б/у корпус",
    "корпус б/у",
    "рассрочк",
    "лизинг",
    "обмен на",
    "куплю",
    "выкуп",
    "стекл",
    "стёкл",
    "чехол",
    "пленк",
    "плёнк",
    "коробк",
)


def avito_thin_junk_reason(ad: dict) -> str | None:
    title = normalize(ad.get("title") or "")
    summary = normalize(ad.get("summary") or "")
    headline = f"{title} {summary}".strip()
    if any(_contains_stem(headline, stem) for stem in AVITO_THIN_JUNK_STEMS):
        return REJECT_THIN_JUNK
    return None
