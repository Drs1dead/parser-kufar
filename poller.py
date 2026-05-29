"""Фоновая рассылка: парсинг Kufar и отправка подходящих объявлений подписчикам."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import InputMediaPhoto

from config import (
    CHECK_INTERVAL,
    FIRST_RUN_LIMIT,
    MARKET_DISCOUNT_THRESHOLD,
    REGULAR_CHECK_INTERVAL,
    VIP_CHECK_INTERVAL,
)
from db import (
    avg_market_price,
    count_seen,
    expire_all_vip,
    get_active_users,
    get_user,
    increment_sent,
    mark_seen,
    prune_price_tables,
    save_market_price,
    seen_links_for,
    set_active,
)
from filters import ad_device_key, is_whole_phone_listing, matches_filters
from formatter import format_ad, truncate_ad_caption
from kufar_fetch import enrich_ads_descriptions, fetch_ads
from logging_setup import log_exception
from user_matching import VIP_SPECIAL_MAX_PRICE, match_ads_for_user

log = logging.getLogger("kufar_bot.poller")

last_run_at: dict[int, float] = {}
first_run_notified: set[int] = set()

VIP_EXPIRED_MSG = (
    "⭐ <b>VIP закончился</b>\n\n"
    "Память сброшена на <b>64 GB</b>. "
    "Модели и лимит цены сохранены — при необходимости продлите VIP в меню."
)
FIRST_RUN_DIGEST_MSG = (
    "ℹ️ Показали первые <b>{n}</b> объявления. "
    "Остальные новые совпадения будут приходить по мере появления на Kufar."
)


def _ingest_market_prices_from_ads(ads: list[dict]) -> None:
    """Пополняет market_prices только целыми телефонами из батча листинга."""
    phone_ads = [ad for ad in ads if is_whole_phone_listing(ad)]
    for ad in phone_ads:
        if not matches_filters(
            ad,
            VIP_SPECIAL_MAX_PRICE,
            [],
            memory_volumes=None,
            smart_filtering=True,
            device_filter=False,
            memory_filter=False,
        ):
            continue
        dk = ad_device_key(ad)
        price = ad.get("price")
        link = ad.get("link")
        if not dk or not isinstance(price, int) or price <= 0:
            continue
        if not isinstance(link, str) or not link.strip():
            continue
        save_market_price(link, dk, price)


def _needs_descriptions(users: list[dict]) -> bool:
    return any(
        u.get("role") == "vip" and (u.get("vip_feed_mode") or "normal") == "exchange"
        for u in users
    )


def _should_process_user(user: dict) -> bool:
    chat_id = user["chat_id"]
    now = asyncio.get_running_loop().time()
    prev = last_run_at.get(chat_id)
    if prev is None:
        return True
    interval = VIP_CHECK_INTERVAL if user.get("role") == "vip" else REGULAR_CHECK_INTERVAL
    return (now - prev) >= interval


async def _notify_vip_expired(bot: Bot, chat_ids: list[int]) -> None:
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, VIP_EXPIRED_MSG, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            set_active(chat_id, False)
        except Exception as exc:
            log_exception(log, "vip expired notify failed chat_id=%s: %s", chat_id, exc)


async def _send_ad(
    bot: Bot,
    chat_id: int,
    ad: dict,
    *,
    market_avg_price: int | None = None,
    below_market: bool = False,
) -> bool:
    text = truncate_ad_caption(
        format_ad(ad, market_avg_price=market_avg_price, below_market=below_market)
    )
    photos = [p for p in (ad.get("photo_urls") or []) if isinstance(p, str) and p.strip()]

    async def _deliver_text() -> None:
        await bot.send_message(chat_id, text, disable_web_page_preview=False)

    async def _deliver_media() -> None:
        media = [
            InputMediaPhoto(
                media=photo,
                caption=text if i == 0 else None,
                parse_mode=ParseMode.HTML if i == 0 else None,
            )
            for i, photo in enumerate(photos[:5])
        ]
        await bot.send_media_group(chat_id=chat_id, media=media)

    async def _deliver() -> None:
        if photos:
            await _deliver_media()
            return
        await _deliver_text()

    try:
        await _deliver()
        return True
    except TelegramRetryAfter as e:
        log.warning("send flood_wait chat_id=%s sec=%s", chat_id, e.retry_after)
        await asyncio.sleep(e.retry_after + 1)
        try:
            await _deliver()
            return True
        except Exception as exc:
            log_exception(log, "send retry failed chat_id=%s: %s", chat_id, exc)
            return False
    except TelegramForbiddenError:
        log.info("user blocked bot chat_id=%s — subscription off", chat_id)
        set_active(chat_id, False)
        return False
    except TelegramBadRequest as exc:
        log.warning("send bad_request chat_id=%s: %s", chat_id, exc)
        if photos:
            try:
                await _deliver_text()
                return True
            except Exception as fallback_exc:
                log_exception(
                    log, "send text fallback failed chat_id=%s: %s", chat_id, fallback_exc
                )
        return False
    except Exception as exc:
        log_exception(log, "send failed chat_id=%s: %s", chat_id, exc)
        return False


async def _process_user(
    bot: Bot,
    user: dict,
    ads: list[dict],
    market_cache: dict[str, int | None],
) -> None:
    chat_id = user["chat_id"]
    is_vip = user.get("role") == "vip"
    feed_mode = (user.get("vip_feed_mode") or "normal") if is_vip else "normal"

    matched = match_ads_for_user(user, ads, market_cache)
    if not matched:
        return

    is_first_run = count_seen(chat_id) == 0
    skipped_first_run = 0
    if is_first_run:
        to_send = matched[:FIRST_RUN_LIMIT]
        skipped_first_run = max(0, len(matched) - FIRST_RUN_LIMIT)
        for ad in matched[FIRST_RUN_LIMIT:]:
            mark_seen(chat_id, ad["link"])
    else:
        to_send = matched

    links = [ad["link"] for ad in to_send if ad.get("link")]
    already_seen = seen_links_for(chat_id, links)

    need_desc = [
        ad
        for ad in to_send
        if not (ad.get("description") or "").strip() and ad.get("link")
    ]
    if need_desc:
        await enrich_ads_descriptions(need_desc)

    for ad in to_send:
        link = ad.get("link")
        if not link or link in already_seen:
            continue

        device_key = ad_device_key(ad)
        price = ad.get("price")
        market_avg = market_cache.get(device_key) if device_key else None
        if is_vip and device_key and market_avg is None:
            market_avg = avg_market_price(device_key)
            market_cache[device_key] = market_avg

        below_market = feed_mode == "below_market"
        if (
            is_vip
            and not below_market
            and market_avg
            and isinstance(price, int)
            and price < int(market_avg * MARKET_DISCOUNT_THRESHOLD)
        ):
            below_market = True

        ok = await _send_ad(
            bot,
            chat_id,
            ad,
            market_avg_price=market_avg if is_vip else None,
            below_market=below_market,
        )
        if ok:
            mark_seen(chat_id, link)
            already_seen.add(link)
            increment_sent(chat_id)
            if device_key and isinstance(price, int) and price > 0:
                save_market_price(ad["link"], device_key, price)
            await asyncio.sleep(0.05)
        else:
            fresh = get_user(chat_id)
            if fresh is None or not fresh.get("active"):
                # Бот заблокирован — дальше не шлём в этом цикле
                break
            log.warning(
                "send not delivered chat_id=%s link=%s",
                chat_id,
                ad.get("link"),
            )

    if (
        is_first_run
        and skipped_first_run > 0
        and chat_id not in first_run_notified
    ):
        first_run_notified.add(chat_id)
        try:
            await bot.send_message(
                chat_id,
                FIRST_RUN_DIGEST_MSG.format(n=FIRST_RUN_LIMIT),
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            log_exception(log, "first-run digest failed chat_id=%s: %s", chat_id, exc)


async def poller(bot: Bot) -> None:
    while True:
        try:
            expired = await asyncio.to_thread(expire_all_vip)
            if expired:
                await _notify_vip_expired(bot, expired)
            pruned = await asyncio.to_thread(prune_price_tables)
            if pruned[0] or pruned[1]:
                log.debug(
                    "price tables pruned market=%s sent=%s", pruned[0], pruned[1]
                )
            users = await asyncio.to_thread(get_active_users, expire_vip=False)
            if not users:
                log.debug("poll skip — no active subscribers")
            else:
                ads = await fetch_ads(with_description=_needs_descriptions(users))
                await asyncio.to_thread(_ingest_market_prices_from_ads, ads)
                market_cache: dict[str, int | None] = {}
                log.debug("poll fetched ads=%d subscribers=%d", len(ads), len(users))

                for user in users:
                    try:
                        if not _should_process_user(user):
                            continue
                        await _process_user(bot, user, ads, market_cache)
                        last_run_at[user["chat_id"]] = asyncio.get_running_loop().time()
                    except Exception:
                        log_exception(log, "poll user failed chat_id=%s", user["chat_id"])
        except Exception:
            log_exception(log, "poll cycle failed")

        await asyncio.sleep(CHECK_INTERVAL)
