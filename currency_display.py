"""Тройное отображение цен по стране: BY — Br · $ · ₽, RU — ₽ · Br · $."""
from __future__ import annotations

import math
from decimal import Decimal

from config import BYN_TO_RUB, BYN_TO_USD, CURRENCY_SIGN, RUB_TO_BYN, RUB_TO_USD
from marketplace.types import COUNTRY_RU, normalize_country


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _fmt_byn(amount: int, *, approx: bool = False) -> str:
    prefix = "≈ " if approx else ""
    return f"{prefix}{_fmt_int(amount)} {CURRENCY_SIGN}"


def _fmt_usd(amount: int, *, approx: bool = True) -> str:
    prefix = "≈ " if approx else ""
    return f"{prefix}{amount}$"


def _fmt_rub(amount: int, *, approx: bool = True) -> str:
    prefix = "≈ " if approx else ""
    return f"{prefix}{_fmt_int(amount)} ₽"


def _ceil_money(value: float) -> int:
    """Ceil вверх для положительных сумм; 0 остаётся 0 (не поднимаем до 1)."""
    if value <= 0:
        return 0
    return max(1, math.ceil(value))


def _triple_from_byn(byn: int, *, price_usd_hint: int | None = None) -> tuple[int, int, int]:
    if byn <= 0:
        return 0, 0, 0
    usd = (
        price_usd_hint
        if price_usd_hint and price_usd_hint > 0
        else _ceil_money(byn * BYN_TO_USD)
    )
    rub = _ceil_money(byn * BYN_TO_RUB)
    return byn, usd, rub


def _triple_from_rub(rub: int) -> tuple[int, int, int]:
    if rub <= 0:
        return 0, 0, 0
    byn = _ceil_money(rub * RUB_TO_BYN)
    usd = _ceil_money(rub * RUB_TO_USD)
    return byn, usd, rub


def _triple_from_usd(usd: int) -> tuple[int, int, int]:
    if usd <= 0:
        return 0, 0, 0
    byn = _ceil_money(usd / BYN_TO_USD) if BYN_TO_USD > 0 else 0
    rub = _ceil_money(usd / RUB_TO_USD) if RUB_TO_USD > 0 else 0
    if rub <= 0 and byn > 0:
        rub = _ceil_money(byn * BYN_TO_RUB)
    return byn, usd, rub


def format_triple_price(
    amount_primary: int,
    *,
    country: str | None = None,
    price_usd_hint: int | None = None,
) -> str:
    """Форматирует цену в трёх валютах с порядком по стране."""
    amount = int(amount_primary)
    if amount <= 0:
        return "договорная"
    c = normalize_country(country)

    if c == COUNTRY_RU:
        rub = amount
        byn, usd, _ = _triple_from_rub(rub)
        return f"{_fmt_rub(rub, approx=False)} · {_fmt_byn(byn)} · {_fmt_usd(usd)}"

    byn = amount
    _, usd, rub = _triple_from_byn(byn, price_usd_hint=price_usd_hint)
    return f"{_fmt_byn(byn)} · {_fmt_usd(usd)} · {_fmt_rub(rub)}"


def format_vip_plan_price(
    usd: int | float,
    *,
    country: str | None = None,
    short: bool = False,
) -> str:
    """Цена VIP-тарифа из USD: порядок валют по стране (BY → Br первым)."""
    usd_i = max(0, int(usd))
    if usd_i <= 0:
        return "договорная"
    byn, _, rub = _triple_from_usd(usd_i)
    usd_s = f"${usd_i}"
    byn_s = _fmt_byn(byn, approx=True)
    rub_s = _fmt_rub(rub, approx=True)
    c = normalize_country(country)
    if c == COUNTRY_RU:
        if short:
            return f"{usd_s} · {rub_s}"
        return f"{rub_s} · {usd_s} · {byn_s}"
    if short:
        return f"{byn_s} · {usd_s}"
    return f"{byn_s} · {usd_s} · {rub_s}"


def format_vip_checkout_price(
    usd: int | float | None,
    amount_rub: str | Decimal | float | None,
    *,
    country: str | None = None,
) -> str:
    """Сумма на экране оплаты: точные ₽ списания + примерные Br/$ по стране."""
    try:
        rub_f = float(amount_rub) if amount_rub is not None and str(amount_rub) != "" else 0.0
    except (TypeError, ValueError):
        rub_f = 0.0
    rub_txt = f"{rub_f:g} ₽" if rub_f > 0 else ""
    usd_i = int(usd) if usd is not None else 0
    byn, _, rub_approx = _triple_from_usd(usd_i) if usd_i > 0 else (0, 0, 0)
    usd_s = f"${usd_i}" if usd_i > 0 else ""
    byn_s = _fmt_byn(byn, approx=True) if byn > 0 else ""
    c = normalize_country(country)

    parts: list[str] = []
    if c == COUNTRY_RU:
        if rub_txt:
            parts.append(rub_txt)
        elif rub_approx > 0:
            parts.append(_fmt_rub(rub_approx, approx=True))
        if usd_s:
            parts.append(usd_s)
        if byn_s:
            parts.append(byn_s)
    else:
        if byn_s:
            parts.append(byn_s)
        if usd_s:
            parts.append(usd_s)
        if rub_txt:
            parts.append(rub_txt)
        elif rub_approx > 0:
            parts.append(_fmt_rub(rub_approx, approx=True))
    return " · ".join(parts) if parts else "—"
