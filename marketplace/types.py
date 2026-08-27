"""Общие типы маркетплейсов (Kufar, Avito)."""
from __future__ import annotations

from typing import Any, NotRequired

SOURCE_KUFAR = "kufar"
SOURCE_AVITO = "avito"
SOURCES = frozenset({SOURCE_KUFAR, SOURCE_AVITO})

COUNTRY_BY = "by"
COUNTRY_RU = "ru"
COUNTRIES = frozenset({COUNTRY_BY, COUNTRY_RU})

CURRENCY_BYN = "BYN"
CURRENCY_RUB = "RUB"

COUNTRY_LABELS: dict[str, str] = {
    COUNTRY_BY: "Беларусь",
    COUNTRY_RU: "Россия",
}

FLAG_BY = "🇧🇾"
FLAG_RU = "🇷🇺"


class NormalizedAd(dict[str, Any]):
    """Нормализованное объявление — dict для совместимости с filters/formatter."""


def normalize_country(value: str | None) -> str:
    key = str(value or "").strip().lower()
    return key if key in COUNTRIES else COUNTRY_BY


def normalize_primary_source(value: str | None) -> str:
    key = str(value or "").strip().lower()
    return key if key in SOURCES else SOURCE_KUFAR


def default_source_for_country(country: str | None) -> str:
    return SOURCE_KUFAR if normalize_country(country) == COUNTRY_BY else SOURCE_AVITO
