"""Фоновая рассылка: парсинг Kufar и отправка подходящих объявлений подписчикам."""
from __future__ import annotations

import asyncio
import logging
import time

import aiohttp

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
    FETCH_CACHE_TTL_SECONDS,
    FIRST_RUN_LIMIT,
    KUFAR_CATALOG_COMPARE,
    KUFAR_USE_CATALOG,
    MARKET_DISCOUNT_THRESHOLD,
    MAX_AD_PHOTOS,
    REGULAR_CHECK_INTERVAL,
    VIP_CHECK_INTERVAL,
)
from db import (
    avg_market_price,
    checkpoint_wal,
    expire_all_vip,
    get_active_users,
    has_seen_any,
    increment_sent,
    mark_seen,
    prune_price_tables,
    prune_seen_ads,
    prune_unknown_market_prices,
    save_market_prices,
    seen_links_for,
    set_active,
    set_poll_last_run,
)
from filters import ad_device_key, is_whole_phone_listing, matches_filters
from filters import ideal_passes
from formatter import format_ad, truncate_ad_caption
from kufar_catalog import FetchKey, fetch_key_for_user, group_users_by_fetch_key
from logging_setup import log_exception
from kufar_fetch import (
    DEFAULT_HEADERS,
    enrich_ads_descriptions,
    fetch_ads,
    fetch_ads_for_key,
)
from product_catalog import is_phones_category
from user_matching import VIP_SPECIAL_MAX_PRICE, match_ads_for_user

log = logging.getLogger("kufar_bot.poller")

first_run_notified: set[int] = set()
_fetch_cache: dict[FetchKey, tuple[float, list[dict]]] = {}

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
    rows: list[tuple[str, str, int]] = []
    for ad in ads:
        if not is_whole_phone_listing(ad):
            continue
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
        rows.append((link, dk, price))
    save_market_prices(rows)


def _is_vip_user(user: dict) -> bool:
    return user.get("role") == "vip"


def _user_interval(user: dict) -> float:
    return float(VIP_CHECK_INTERVAL if _is_vip_user(user) else REGULAR_CHECK_INTERVAL)


def _user_last_run(user: dict) -> float:
    if _is_vip_user(user):
        return float(user.get("poll_last_vip") or 0)
    return float(user.get("poll_last_regular") or 0)


def _seconds_until_due(user: dict, now: float) -> float:
    prev = _user_last_run(user)
    if prev <= 0:
        return 0.0
    return max(0.0, _user_interval(user) - (now - prev))


def _should_process_user(user: dict, *, now: float | None = None) -> bool:
    t = time.time() if now is None else now
    return _seconds_until_due(user, t) <= 0.0


def _poll_sleep_seconds(
    users: list[dict],
    now: float,
    *,
    tick: float | None = None,
) -> float:
    """Сколько спать до следующего прохода: не дольше тика, не позже due."""
    cap = float(CHECK_INTERVAL if tick is None else tick)
    cap = max(0.05, cap)
    if not users:
        return cap
    soonest = min(_seconds_until_due(user, now) for user in users)
    if soonest <= 0:
        return 0.05
    return min(cap, soonest)


def _mark_user_polled(user: dict) -> None:
    is_vip = _is_vip_user(user)
    set_poll_last_run(user["chat_id"], is_vip=is_vip)
    stamped = int(time.time())
    if is_vip:
        user["poll_last_vip"] = stamped
    else:
        user["poll_last_regular"] = stamped


async def _notify_vip_expired(bot: Bot, chat_ids: list[int]) -> None:
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, VIP_EXPIRED_MSG, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            set_active(chat_id, False)
        except Exception as exc:
            log_exception(log, "vip expired notify failed chat_id=%s: %s", chat_id, exc)


def _is_unreachable_chat(exc: TelegramBadRequest) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "chat not found",
            "user is deactivated",
            "peer_id_invalid",
            "bot was blocked",
        )
    )


async def _send_ad(
    bot: Bot,
    chat_id: int,
    ad: dict,
    *,
    market_avg_price: int | None = None,
    below_market: bool = False,
    ideal_feed: bool = False,
    include_photos: bool = False,
) -> tuple[bool, bool]:
    """(доставлено, пользователь отключён — блокировка бота)."""
    text = truncate_ad_caption(
        format_ad(
            ad,
            market_avg_price=market_avg_price,
            below_market=below_market,
            ideal_feed=ideal_feed,
        )
    )
    photos = [p for p in (ad.get("photo_urls") or []) if isinstance(p, str) and p.strip()]
    if include_photos and photos:
        photos = photos[:MAX_AD_PHOTOS]

    async def _deliver_text() -> None:
        await bot.send_message(chat_id, text, disable_web_page_preview=False)

    async def _deliver_media() -> None:
        media = [
            InputMediaPhoto(
                media=photo,
                caption=text if i == 0 else None,
                parse_mode=ParseMode.HTML if i == 0 else None,
            )
            for i, photo in enumerate(photos)
        ]
        await bot.send_media_group(chat_id=chat_id, media=media)

    async def _deliver() -> None:
        if include_photos and photos:
            await _deliver_media()
            return
        await _deliver_text()

    try:
        await _deliver()
        return True, False
    except TelegramRetryAfter as e:
        log.warning("send flood_wait chat_id=%s sec=%s", chat_id, e.retry_after)
        await asyncio.sleep(e.retry_after + 1)
        try:
            await _deliver()
            return True, False
        except Exception as exc:
            log_exception(log, "send retry failed chat_id=%s: %s", chat_id, exc)
            return False, False
    except TelegramForbiddenError:
        log.info("user blocked bot chat_id=%s — subscription off", chat_id)
        set_active(chat_id, False)
        return False, True
    except TelegramBadRequest as exc:
        if _is_unreachable_chat(exc):
            log.info("user unreachable chat_id=%s — subscription off", chat_id)
            set_active(chat_id, False)
            return False, True
        log.warning("send bad_request chat_id=%s: %s", chat_id, exc)
        if photos and include_photos:
            try:
                await _deliver_text()
                return True, False
            except Exception as fallback_exc:
                log_exception(
                    log, "send text fallback failed chat_id=%s: %s", chat_id, fallback_exc
                )
        return False, False
    except Exception as exc:
        log_exception(log, "send failed chat_id=%s: %s", chat_id, exc)
        return False, False


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

    is_first_run = not has_seen_any(chat_id)
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

    ideal_mode = is_vip and feed_mode == "ideal"
    need_desc = [
        ad
        for ad in to_send
        if ad.get("link")
        and ad["link"] not in already_seen
        and not (ad.get("description") or "").strip()
    ]
    if need_desc:
        await enrich_ads_descriptions(need_desc)

    if ideal_mode:
        strict_ok: list[dict] = []
        for ad in to_send:
            link = ad.get("link")
            if not link or link in already_seen:
                continue
            if ideal_passes(
                ad, stage="strict", skip_battery=not is_phones_category(user.get("product_category"))
            ):
                strict_ok.append(ad)
            else:
                mark_seen(chat_id, link)
                already_seen.add(link)
        to_send = strict_ok
        if not to_send:
            return

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
            and feed_mode != "ideal"
            and market_avg
            and isinstance(price, int)
            and price < int(market_avg * MARKET_DISCOUNT_THRESHOLD)
        ):
            below_market = True

        ok, deactivated = await _send_ad(
            bot,
            chat_id,
            ad,
            market_avg_price=market_avg if is_vip else None,
            below_market=below_market,
            ideal_feed=ideal_mode,
            include_photos=is_vip,
        )
        if ok:
            mark_seen(chat_id, link)
            already_seen.add(link)
            increment_sent(chat_id)
            await asyncio.sleep(0.05)
        elif deactivated:
            user["active"] = False
            break
        else:
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


async def _fetch_catalog_groups(
    groups: dict[FetchKey, list[dict]],
) -> tuple[dict[FetchKey, list[dict]], list[dict]]:
    keys = list(groups.keys())
    if not keys:
        return {}, []
    now = time.time()
    ads_by_key: dict[FetchKey, list[dict]] = {}
    keys_to_fetch: list[FetchKey] = []
    for key in keys:
        cached = _fetch_cache.get(key)
        if cached and now - cached[0] < FETCH_CACHE_TTL_SECONDS:
            ads_by_key[key] = cached[1]
        else:
            keys_to_fetch.append(key)

    if keys_to_fetch:
        connector = aiohttp.TCPConnector(limit=8)
        async with aiohttp.ClientSession(
            headers=DEFAULT_HEADERS, connector=connector
        ) as session:
            batches = await asyncio.gather(
                *(
                    fetch_ads_for_key(
                        category,
                        rgn,
                        ar,
                        models,
                        memories,
                        session=session,
                    )
                    for category, rgn, ar, models, memories in keys_to_fetch
                )
            )
        for key, ads in zip(keys_to_fetch, batches):
            _fetch_cache[key] = (now, ads)
            ads_by_key[key] = ads

    merged: list[dict] = []
    seen_links: set[str] = set()
    for key in keys:
        for ad in ads_by_key.get(key) or []:
            link = ad.get("link")
            if not isinstance(link, str) or not link or link in seen_links:
                continue
            seen_links.add(link)
            merged.append(ad)
    return ads_by_key, merged


async def _dispatch_due(
    bot: Bot,
    due: list[dict],
    *,
    compare_catalog: bool = False,
) -> None:
    if not due:
        return
    if KUFAR_USE_CATALOG:
        groups = group_users_by_fetch_key(due)
        ads_by_key, merged = await _fetch_catalog_groups(groups)
        if compare_catalog and KUFAR_CATALOG_COMPARE:
            text_ads = await fetch_ads()
            log.info(
                "kufar catalog compare catalog=%d text=%d keys=%d",
                len(merged),
                len(text_ads),
                len(groups),
            )
        await asyncio.to_thread(_ingest_market_prices_from_ads, merged)
        market_cache: dict[str, int | None] = {}
        log.info(
            "poll catalog ads=%d keys=%d due=%d",
            len(merged),
            len(groups),
            len(due),
        )
        for user in due:
            try:
                key = fetch_key_for_user(user)
                ads = ads_by_key.get(key) or []
                await _process_user(bot, user, ads, market_cache)
                _mark_user_polled(user)
            except Exception:
                log_exception(log, "poll user failed chat_id=%s", user["chat_id"])
        return

    ads = await fetch_ads()
    await asyncio.to_thread(_ingest_market_prices_from_ads, ads)
    market_cache = {}
    log.info("poll fetched ads=%d due=%d", len(ads), len(due))
    for user in due:
        try:
            await _process_user(bot, user, ads, market_cache)
            _mark_user_polled(user)
        except Exception:
            log_exception(log, "poll user failed chat_id=%s", user["chat_id"])


async def poller(bot: Bot) -> None:
    # Тяжёлые операции (expire/prune) не обязательно делать каждый цикл.
    # Это снижает нагрузку на SQLite при большом количестве пользователей.
    last_expire_at = 0.0
    last_prune_at = 0.0
    expire_every_s = max(60.0, CHECK_INTERVAL)  # не чаще раза в минуту
    prune_every_s = max(600.0, CHECK_INTERVAL * 10)  # примерно раз в 10 минут

    while True:
        users: list[dict] = []
        try:
            now = time.time()
            if now - last_expire_at >= expire_every_s:
                expired = await asyncio.to_thread(expire_all_vip)
                last_expire_at = now
                if expired:
                    await _notify_vip_expired(bot, expired)

            if now - last_prune_at >= prune_every_s:
                pruned = await asyncio.to_thread(prune_price_tables)
                if pruned[0] or pruned[1]:
                    log.debug(
                        "price tables pruned market=%s sent=%s", pruned[0], pruned[1]
                    )
                seen_pruned = await asyncio.to_thread(prune_seen_ads)
                if seen_pruned:
                    log.debug("seen_ads pruned deleted=%s", seen_pruned)
                stale = await asyncio.to_thread(prune_unknown_market_prices)
                if stale:
                    log.debug("market_prices unknown models deleted=%s", stale)
                await asyncio.to_thread(checkpoint_wal)
                last_prune_at = now

            users = await asyncio.to_thread(get_active_users, expire_vip=False)
            now = time.time()
            vip_due = [
                u for u in users if _is_vip_user(u) and _should_process_user(u, now=now)
            ]
            regular_due = [
                u
                for u in users
                if not _is_vip_user(u) and _should_process_user(u, now=now)
            ]
            if not vip_due and not regular_due:
                log.debug("poll skip — no due subscribers")
            else:
                # VIP отдельно: не ждёт fetch ключей обычных пользователей.
                await _dispatch_due(bot, vip_due, compare_catalog=False)
                await _dispatch_due(bot, regular_due)
        except Exception:
            log_exception(log, "poll cycle failed")

        await asyncio.sleep(_poll_sleep_seconds(users, time.time()))
