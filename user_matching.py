"""Сопоставление объявлений Kufar с фильтрами пользователя (ядро рассылки)."""
from __future__ import annotations

from collections.abc import Callable

from config import FILTER_DEBUG_LOG, MARKET_DISCOUNT_THRESHOLD
from db import avg_market_price
from filters import (
    ad_device_key,
    exchange_reject_reason,
    filter_reject_reason,
    ideal_passes,
    ideal_reject_reason,
    log_filter_reject,
    matches_filters,
)

# VIP-потоки «ниже рынка» / «обмен» — без лимита цены из профиля
VIP_SPECIAL_MAX_PRICE = 99_999_999


def _smart_filtering_for(user: dict) -> bool:
    """Жёсткий отбор (целый телефон, не продажа, «новый» и т.д.) — только для VIP."""
    return user.get("role") == "vip"


def _passes_base(ad: dict, user: dict, *, max_price: int, skip_new_phone: bool = False) -> bool:
    return matches_filters(
        ad,
        max_price,
        user["keywords"],
        memory_volumes=user.get("memory_volumes"),
        smart_filtering=_smart_filtering_for(user),
        device_filter=True,
        memory_filter=True,
        skip_new_phone=skip_new_phone,
    )


def _log_reject(ad: dict, user: dict, *, max_price: int, feed_mode: str) -> None:
    if not FILTER_DEBUG_LOG:
        return
    reason = filter_reject_reason(
        ad,
        max_price,
        user["keywords"],
        memory_volumes=user.get("memory_volumes"),
        smart_filtering=_smart_filtering_for(user),
        device_filter=True,
        memory_filter=True,
    )
    if reason:
        log_filter_reject(ad, reason, chat_id=user["chat_id"], feed_mode=feed_mode)


def _market_avg(device_key: str, cache: dict[str, int | None]) -> int | None:
    if device_key in cache:
        return cache[device_key]
    value = avg_market_price(device_key)
    cache[device_key] = value
    return value


def _match_vip_ads(
    user: dict,
    ads: list[dict],
    market_cache: dict[str, int | None],
    feed_mode: str,
    *,
    accept: Callable[[dict, dict, dict[str, int | None]], bool],
) -> list[dict]:
    matched: list[dict] = []
    skip_new = feed_mode == "ideal"
    for ad in ads:
        if not _passes_base(
            ad, user, max_price=VIP_SPECIAL_MAX_PRICE, skip_new_phone=skip_new
        ):
            _log_reject(ad, user, max_price=VIP_SPECIAL_MAX_PRICE, feed_mode=feed_mode)
            continue
        if accept(ad, user, market_cache):
            matched.append(ad)
    return matched


def _below_market_accept(ad: dict, user: dict, market_cache: dict[str, int | None]) -> bool:
    dk = ad_device_key(ad)
    price = ad.get("price")
    if not dk or not isinstance(price, int) or price <= 0:
        return False
    mavg = _market_avg(dk, market_cache)
    return bool(mavg and price < int(mavg * MARKET_DISCOUNT_THRESHOLD))


def _ideal_pre_accept(ad: dict, user: dict, market_cache: dict[str, int | None]) -> bool:
    del market_cache
    if not ideal_passes(ad, stage="pre"):
        reason = ideal_reject_reason(ad, require_full_text=False)
        if reason:
            log_filter_reject(
                ad,
                reason,
                chat_id=user["chat_id"],
                feed_mode="ideal",
            )
        return False
    return True


def _exchange_accept(ad: dict, user: dict, market_cache: dict[str, int | None]) -> bool:
    reason = exchange_reject_reason(ad)
    if reason:
        log_filter_reject(
            ad,
            reason,
            chat_id=user["chat_id"],
            feed_mode=(user.get("vip_feed_mode") or "normal"),
        )
        return False
    return True


def match_ads_for_user(
    user: dict,
    ads: list[dict],
    market_cache: dict[str, int | None],
) -> list[dict]:
    """Возвращает объявления, подходящие пользователю под его VIP-поток и фильтры."""
    is_vip = user.get("role") == "vip"
    feed_mode = (user.get("vip_feed_mode") or "normal") if is_vip else "normal"

    if is_vip and feed_mode == "below_market":
        return _match_vip_ads(
            user,
            ads,
            market_cache,
            feed_mode,
            accept=_below_market_accept,
        )

    if is_vip and feed_mode == "exchange":
        return _match_vip_ads(
            user,
            ads,
            market_cache,
            feed_mode,
            accept=_exchange_accept,
        )

    if is_vip and feed_mode == "ideal":
        return _match_vip_ads(
            user,
            ads,
            market_cache,
            feed_mode,
            accept=_ideal_pre_accept,
        )

    max_price = int(user.get("max_price") or 0)
    out: list[dict] = []
    for ad in ads:
        if _passes_base(ad, user, max_price=max_price):
            out.append(ad)
        else:
            _log_reject(ad, user, max_price=max_price, feed_mode=feed_mode)
    return out
