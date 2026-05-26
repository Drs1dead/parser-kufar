"""Сопоставление объявлений Kufar с фильтрами пользователя (ядро рассылки)."""
from __future__ import annotations

from config import FILTER_DEBUG_LOG, MARKET_DISCOUNT_THRESHOLD
from db import avg_market_price
from filters import (
    ad_device_key,
    exchange_reject_reason,
    filter_reject_reason,
    log_filter_reject,
    matches_filters,
)

# VIP-потоки «ниже рынка» / «обмен» — без лимита цены из профиля
VIP_SPECIAL_MAX_PRICE = 99_999_999


def _passes_base(ad: dict, user: dict, *, max_price: int) -> bool:
    return matches_filters(
        ad,
        max_price,
        user["keywords"],
        memory_volumes=user.get("memory_volumes"),
        smart_filtering=True,
        device_filter=True,
        memory_filter=True,
    )


def _log_reject(ad: dict, user: dict, *, max_price: int, feed_mode: str) -> None:
    if not FILTER_DEBUG_LOG:
        return
    reason = filter_reject_reason(
        ad,
        max_price,
        user["keywords"],
        memory_volumes=user.get("memory_volumes"),
        smart_filtering=True,
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


def match_ads_for_user(
    user: dict,
    ads: list[dict],
    market_cache: dict[str, int | None],
) -> list[dict]:
    """Возвращает объявления, подходящие пользователю под его VIP-поток и фильтры."""
    chat_id = user["chat_id"]
    is_vip = user.get("role") == "vip"
    feed_mode = (user.get("vip_feed_mode") or "normal") if is_vip else "normal"

    if is_vip and feed_mode == "below_market":
        matched: list[dict] = []
        for ad in ads:
            if not _passes_base(ad, user, max_price=VIP_SPECIAL_MAX_PRICE):
                _log_reject(ad, user, max_price=VIP_SPECIAL_MAX_PRICE, feed_mode=feed_mode)
                continue
            dk = ad_device_key(ad)
            price = ad.get("price")
            if not dk or not isinstance(price, int) or price <= 0:
                continue
            mavg = _market_avg(dk, market_cache)
            if mavg and price < int(mavg * MARKET_DISCOUNT_THRESHOLD):
                matched.append(ad)
        return matched

    if is_vip and feed_mode == "exchange":
        matched = []
        for ad in ads:
            if not _passes_base(ad, user, max_price=VIP_SPECIAL_MAX_PRICE):
                _log_reject(ad, user, max_price=VIP_SPECIAL_MAX_PRICE, feed_mode=feed_mode)
                continue
            if exchange_reject_reason(ad):
                log_filter_reject(ad, exchange_reject_reason(ad) or "", chat_id=chat_id, feed_mode=feed_mode)
                continue
            matched.append(ad)
        return matched

    max_price = int(user.get("max_price") or 0)
    out: list[dict] = []
    for ad in ads:
        if _passes_base(ad, user, max_price=max_price):
            out.append(ad)
        else:
            _log_reject(ad, user, max_price=max_price, feed_mode=feed_mode)
    return out
