"""Меню: главная, цена, память, VIP, пауза, промокод."""
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import (
    CURRENCY_SIGN,
    DEFAULT_MEMORY_VOLUMES,
    MAX_PRICE_PRESETS,
    MEMORY_VOLUME_OPTIONS,
)
from kufar_catalog import QUICK_RGN_BUTTONS
from kufar_geo import search_places
from product_catalog import is_phones_category
from db import (
    get_user,
    redeem_promo_code,
    set_active,
    set_vip,
    update_city,
    update_geo,
    update_max_price,
    update_memory_volumes,
    update_vip_feed_mode,
)
from bot_ui import (
    HELP_TEXT,
    back_keyboard,
    back_row,
    city_keyboard,
    city_pick_keyboard,
    city_screen_text,
    city_typed_prompt_text,
    custom_price_prompt_text,
    help_keyboard,
    home_keyboard,
    home_text,
    memory_keyboard,
    memory_screen_text,
    price_screen_text,
    promo_back_keyboard,
    promo_prompt_text,
    vip_keyboard,
    vip_text,
)
from handlers.goods_ui import (
    _goods_categories_keyboard,
    _goods_categories_text,
)
from handlers.admin import admin_home_text, admin_main_keyboard
from handlers.helpers import (
    actor_user_id,
    is_admin,
    is_vip_user,
    load_user_from_message,
    flush_screen,
    require_user_cb,
    safe_cb_answer,
    safe_edit_message,
    sync_username_from_callback,
)
from handlers.states import CityInputState, CustomPriceState, PromoCodeState
from logging_setup import log_exception

log = logging.getLogger(__name__)
router = Router()

def price_presets_keyboard(user: dict | None) -> InlineKeyboardMarkup:
    cur = user.get("max_price") if user else None
    row: list[InlineKeyboardButton] = []
    rows: list[list[InlineKeyboardButton]] = []
    for p in MAX_PRICE_PRESETS:
        short = f"{p} {CURRENCY_SIGN}"
        label = f"✅ {short}" if cur is not None and int(cur) == int(p) else short
        row.append(InlineKeyboardButton(text=label, callback_data=f"nav:set:{p}"))
        if len(row) >= 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if is_vip_user(user):
        rows.append([InlineKeyboardButton(text="🎯 Своя цена (VIP)", callback_data="nav:price:custom")])
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(lambda c: (c.data or "").startswith("mem:t:"))
async def on_memory_toggle(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    user = await require_user_cb(cb)
    if user is None:
        return
    chat_id = cb.message.chat.id
    vol = (cb.data or "")[6:]
    if vol not in MEMORY_VOLUME_OPTIONS:
        await cb.answer("Неизвестный объём", show_alert=True)
        return

    current = list(user.get("memory_volumes") or DEFAULT_MEMORY_VOLUMES)
    selected = set(current)
    if is_vip_user(user):
        if vol in selected:
            if len(selected) <= 1:
                await cb.answer("Нельзя снять последний объём (минимум 64 GB)", show_alert=True)
                return
            selected.remove(vol)
        else:
            selected.add(vol)
        new_vols = [v for v in MEMORY_VOLUME_OPTIONS if v in selected]
    else:
        new_vols = [vol]

    user["memory_volumes"] = update_memory_volumes(chat_id, new_vols)
    await flush_screen(
        cb,
        memory_screen_text(user),
        reply_markup=memory_keyboard(user),
        notice="💾 Сохранено",
    )


@router.callback_query(lambda c: (c.data or "").startswith("city:rgn:"))
async def on_city_region(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.message is None:
        await cb.answer()
        return
    user = await require_user_cb(cb)
    if user is None:
        return
    chat_id = cb.message.chat.id
    raw = (cb.data or "")[9:]
    if not raw.isdigit():
        await cb.answer("Неизвестный регион", show_alert=True)
        return
    rgn = int(raw)
    label = next((lbl for rg, lbl in QUICK_RGN_BUTTONS if rg == rgn), "")
    if not label:
        await cb.answer("Неизвестный регион", show_alert=True)
        return
    await state.clear()
    geo = update_geo(chat_id, rgn, None, label)
    user.update(geo)
    await flush_screen(
        cb,
        city_screen_text(user),
        reply_markup=city_keyboard(user),
        notice="📍 Сохранено",
    )


@router.callback_query(lambda c: (c.data or "").startswith("city:pick:"))
async def on_city_pick(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.message is None:
        await cb.answer()
        return
    user = await require_user_cb(cb)
    if user is None:
        return
    chat_id = cb.message.chat.id
    raw = (cb.data or "")[10:]
    if not raw.isdigit():
        await cb.answer("Неизвестный вариант", show_alert=True)
        return
    idx = int(raw)
    data = await state.get_data()
    options = data.get("city_options") or []
    if idx < 0 or idx >= len(options):
        await cb.answer("Список устарел — введите город снова", show_alert=True)
        return
    opt = options[idx]
    geo = update_geo(
        chat_id,
        int(opt["rgn"]),
        int(opt["ar"]),
        str(opt.get("label") or ""),
    )
    user.update(geo)
    await state.clear()
    await flush_screen(
        cb,
        home_text(user, is_new=False),
        reply_markup=home_keyboard(
            is_admin=is_admin(cb.from_user.id if cb.from_user else 0),
            user=user,
        ),
        notice=f"📍 {geo['city_label']}",
    )


@router.callback_query(lambda c: (c.data or "").startswith("city:t:"))
async def on_city_select(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    user = await require_user_cb(cb)
    if user is None:
        return
    chat_id = cb.message.chat.id
    slug = (cb.data or "")[7:]
    from kufar_catalog import CITY_RGN

    if slug not in CITY_RGN:
        await cb.answer("Неизвестный город", show_alert=True)
        return

    user["city"] = update_city(chat_id, slug)
    await flush_screen(
        cb,
        city_screen_text(user),
        reply_markup=city_keyboard(user),
        notice="📍 Сохранено",
    )


@router.callback_query(lambda c: (c.data or "").startswith("nav:"))
async def on_nav_callback(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    uid = cb.from_user.id if cb.from_user else 0
    data = (cb.data or "").strip()
    parts = data.split(":")

    user = get_user(chat_id)
    if user is not None:
        sync_username_from_callback(user, cb)
    user_is_admin = is_admin(uid)

    try:
        if data == "nav:home":
            await state.clear()
            if user is None:
                await cb.answer()
                await safe_edit_message(
                    cb,
                    "Сначала нажмите <code>/start</code>.",
                    reply_markup=None,
                )
                return
            await flush_screen(
                cb,
                home_text(user, is_new=False),
                reply_markup=home_keyboard(is_admin=user_is_admin, user=user),
            )
            return

        if user is None:
            await cb.answer("Сначала /start", show_alert=True)
            return

        if data == "nav:resume":
            if user.get("active"):
                await cb.answer("Уведомления уже включены")
                return
            if not (user.get("keywords") or []):
                await cb.answer(
                    "Сначала выберите модели в «Товары» — иначе искать нечего.",
                    show_alert=True,
                )
                return
            set_active(chat_id, True)
            log.debug("resume chat_id=%s", chat_id)
            user["active"] = True
            await flush_screen(
                cb,
                home_text(user, is_new=False),
                reply_markup=home_keyboard(is_admin=user_is_admin, user=user),
                notice="🔔 Уведомления включены",
            )
            return

        if data in ("nav:vipf:bm", "nav:vipf:ex", "nav:vipf:ideal"):
            if user.get("role") != "vip":
                await cb.answer("Только для VIP", show_alert=True)
                return
            cur = user.get("vip_feed_mode") or "normal"
            if data == "nav:vipf:bm":
                new_mode = "normal" if cur == "below_market" else "below_market"
            elif data == "nav:vipf:ex":
                new_mode = "normal" if cur == "exchange" else "exchange"
            else:
                new_mode = "normal" if cur == "ideal" else "ideal"
            update_vip_feed_mode(chat_id, new_mode)
            user["vip_feed_mode"] = new_mode
            hint = (
                "🔥 Поток «ниже рынка»"
                if new_mode == "below_market"
                else (
                    "🔄 Поток «обмен»"
                    if new_mode == "exchange"
                    else (
                        "✨ Поток «идеальные»"
                        if new_mode == "ideal"
                        else "📬 Обычная рассылка"
                    )
                )
            )
            await flush_screen(
                cb,
                vip_text(user),
                reply_markup=vip_keyboard(user),
                notice=hint,
            )
            return

        if data == "nav:goods":
            await flush_screen(
                cb,
                _goods_categories_text(user),
                reply_markup=_goods_categories_keyboard(user),
            )
            return

        if data == "nav:price":
            await state.clear()
            await flush_screen(
                cb,
                price_screen_text(user),
                reply_markup=price_presets_keyboard(user),
            )
            return

        if data == "nav:memory":
            if not is_phones_category(user.get("product_category")):
                await cb.answer("Память только для смартфонов", show_alert=True)
                return
            await state.clear()
            await flush_screen(
                cb,
                memory_screen_text(user),
                reply_markup=memory_keyboard(user),
            )
            return

        if data == "nav:city":
            await state.clear()
            await flush_screen(
                cb,
                city_screen_text(user),
                reply_markup=city_keyboard(user),
            )
            return

        if data == "nav:city:typed":
            await state.set_state(CityInputState.waiting_text)
            await flush_screen(
                cb,
                city_typed_prompt_text(),
                reply_markup=back_keyboard(),
            )
            return

        if data == "nav:price:custom":
            if not is_vip_user(user):
                await cb.answer("Только для VIP", show_alert=True)
                return
            await state.set_state(CustomPriceState.waiting_price)
            await flush_screen(
                cb,
                custom_price_prompt_text(),
                reply_markup=back_keyboard(),
            )
            return

        if len(parts) == 3 and parts[0] == "nav" and parts[1] == "set" and parts[2].isdigit():
            price = int(parts[2])
            if 1 <= price <= 10_000_000:
                user["max_price"] = update_max_price(chat_id, price)
            await flush_screen(
                cb,
                price_screen_text(user),
                reply_markup=price_presets_keyboard(user),
                notice="💰 Лимит сохранён",
            )
            return

        if data == "nav:promo":
            await state.set_state(PromoCodeState.waiting_code)
            await flush_screen(
                cb,
                promo_prompt_text(),
                reply_markup=promo_back_keyboard(),
            )
            return

        if data == "nav:vip":
            await flush_screen(
                cb,
                vip_text(user),
                reply_markup=vip_keyboard(user),
            )
            return

        if data == "nav:help":
            await flush_screen(
                cb,
                HELP_TEXT,
                reply_markup=help_keyboard(),
            )
            return

        if data == "nav:stop":
            set_active(chat_id, False)
            log.debug("stop chat_id=%s", chat_id)
            user["active"] = False
            await flush_screen(
                cb,
                home_text(user, is_new=False),
                reply_markup=home_keyboard(is_admin=user_is_admin, user=user),
                notice="🔕 На паузе",
            )
            return

        if data == "nav:admin":
            if not user_is_admin:
                await cb.answer("Нет доступа", show_alert=True)
                return
            await state.clear()
            await flush_screen(
                cb,
                admin_home_text(),
                reply_markup=admin_main_keyboard(),
            )
            return

        await cb.answer("Неизвестное действие", show_alert=True)
    except Exception:
        log_exception(log, "nav error data=%s", data)
        await safe_cb_answer(cb, "Не удалось обновить меню", show_alert=True)


@router.message(CityInputState.waiting_text, F.text, ~F.text.startswith("/"))
async def on_city_text(msg: Message, state: FSMContext) -> None:
    chat_id = msg.chat.id
    user = load_user_from_message(msg)
    if user is None:
        await state.clear()
        await msg.answer("Сначала нажми <code>/start</code>.", parse_mode=ParseMode.HTML)
        return

    text = (msg.text or "").strip()
    if len(text) < 2:
        await msg.answer(
            "Введите не менее 2 символов, например <code>Брест</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    matches = search_places(text, limit=5)
    if not matches:
        await msg.answer(
            "Ничего не найдено. Попробуйте другое название или выберите область в меню.",
            parse_mode=ParseMode.HTML,
            reply_markup=city_keyboard(user),
        )
        return

    if len(matches) == 1:
        place = matches[0]
        geo = update_geo(chat_id, place.rgn, place.ar, place.label)
        user.update(geo)
        await state.clear()
        uid = actor_user_id(msg)
        await msg.answer(
            home_text(user, is_new=False),
            reply_markup=home_keyboard(is_admin=is_admin(uid), user=user),
            parse_mode=ParseMode.HTML,
        )
        return

    if len(matches) <= 3:
        options = [
            {
                "label": f"{p.label} ({p.region_label})",
                "rgn": p.rgn,
                "ar": p.ar,
            }
            for p in matches[:3]
        ]
        await state.update_data(city_options=options)
        await msg.answer(
            "Найдено несколько вариантов — выберите:",
            reply_markup=city_pick_keyboard(options),
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.answer(
        "Слишком много совпадений — уточните название.",
        parse_mode=ParseMode.HTML,
        reply_markup=city_keyboard(user),
    )


@router.message(CustomPriceState.waiting_price, F.text, ~F.text.startswith("/"))
async def on_custom_price_text(msg: Message, state: FSMContext) -> None:
    chat_id = msg.chat.id
    user = load_user_from_message(msg)
    if user is None:
        await state.clear()
        await msg.answer("Сначала нажми <code>/start</code>.", parse_mode=ParseMode.HTML)
        return
    if not is_vip_user(user):
        await state.clear()
        await msg.answer("Индивидуальная цена доступна только для VIP.", parse_mode=ParseMode.HTML)
        return

    raw = (msg.text or "").strip().replace(" ", "")
    if not raw.isdigit():
        await msg.answer(
            "Введите цену одним числом, например <code>1200</code>.",
            parse_mode=ParseMode.HTML,
        )
        return
    price = int(raw)
    if not 1 <= price <= 10_000_000:
        await msg.answer(
            f"Цена должна быть от 1 до 10 000 000 {CURRENCY_SIGN}. Введите значение заново.",
            parse_mode=ParseMode.HTML,
        )
        return

    user["max_price"] = update_max_price(chat_id, price)
    await state.clear()
    await msg.answer(
        price_screen_text(user),
        reply_markup=price_presets_keyboard(user),
        parse_mode=ParseMode.HTML,
    )


@router.message(PromoCodeState.waiting_code, F.text, ~F.text.startswith("/"))
async def on_promo_code_text(msg: Message, state: FSMContext) -> None:
    chat_id = msg.chat.id
    user = load_user_from_message(msg)
    if user is None:
        await state.clear()
        await msg.answer(
            "Сначала нажми <code>/start</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    status, days = redeem_promo_code(chat_id, msg.text or "")
    if status == "ok" and days is not None:
        set_vip(chat_id, days=days)
        await state.clear()
        user = get_user(chat_id) or user
        uid = actor_user_id(msg)
        await msg.answer(
            f"🎉 Промокод принят! VIP на <b>{days}</b> дн. — настройте бот в меню.",
            reply_markup=home_keyboard(is_admin=is_admin(uid), user=user),
            parse_mode=ParseMode.HTML,
        )
        return

    if status == "exhausted":
        await msg.answer(
            "❌ Промокод исчерпан (лимит активаций). Попробуйте другой:",
            reply_markup=promo_back_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if status == "already_used":
        await msg.answer(
            "❌ Промокод уже был использован. Попробуйте другой:",
            reply_markup=promo_back_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.answer(
        "❌ Промокод не найден. Проверьте и отправьте снова:",
        reply_markup=promo_back_keyboard(),
        parse_mode=ParseMode.HTML,
    )
