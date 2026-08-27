"""Тройное отображение цен по стране: BY — Br · $ · ₽, RU — ₽ · Br · $."""
from __future__ import annotations

from config import BYN_TO_RUB, BYN_TO_USD, CURRENCY_SIGN, RUB_TO_BYN, RUB_TO_USD
from marketplace.types import COUNTRY_BY, COUNTRY_RU, normalize_country


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _fmt_byn(amount: int) -> str:
    return f"{_fmt_int(amount)} {CURRENCY_SIGN}"


def _fmt_usd(amount: int) -> str:
    return f"≈ {amount}$"


def _fmt_rub(amount: int, *, approx: bool = True) -> str:
    prefix = "≈ " if approx else ""
    return f"{prefix}{_fmt_int(amount)} ₽"


def _triple_from_byn(byn: int, *, price_usd_hint: int | None = None) -> tuple[int, int, int]:
    usd = price_usd_hint if price_usd_hint and price_usd_hint > 0 else max(
        1, round(byn * BYN_TO_USD)
    )
    rub = max(1, round(byn * BYN_TO_RUB))
    return byn, usd, rub


def _triple_from_rub(rub: int) -> tuple[int, int, int]:
    byn = max(1, round(rub * RUB_TO_BYN))
    usd = max(1, round(rub * RUB_TO_USD))
    return byn, usd, rub


def format_triple_price(
    amount_primary: int,
    *,
    country: str | None = None,
    price_usd_hint: int | None = None,
) -> str:
    """Форматирует цену в трёх валютах с порядком по стране."""
    amount = max(0, int(amount_primary))
    c = normalize_country(country)

    if c == COUNTRY_RU:
        rub = amount
        byn, usd, _ = _triple_from_rub(rub)
        return f"{_fmt_rub(rub, approx=False)} · {_fmt_byn(byn)} · {_fmt_usd(usd)}"

    byn, usd, rub = _triple_from_byn(amount, price_usd_hint=price_usd_hint)
    return f"{_fmt_byn(byn)} · {_fmt_usd(usd)} · {_fmt_rub(rub)}"
