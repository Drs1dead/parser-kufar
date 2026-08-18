"""Callback-кнопки выбора моделей (goods, bulk, gt, st)."""
import logging
from collections.abc import Callable

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from config import DEVICE_CATALOG
from goods_tree import (
    APPLE_LINES,
    GOODS_PER_PAGE,
    LINE_LABELS,
    SAMSUNG_LINE_LABELS,
    SAMSUNG_LINES,
    SAMSUNG_SERIES_LABELS,
)
from db import update_keywords
from bot_ui import home_keyboard, home_text
from handlers.goods_ui import (
    _apple_models,
    _goods_apple_lines_keyboard,
    _goods_apple_lines_text,
    _goods_line_keyboard,
    _goods_line_pick_text,
    _goods_mobile_brands_keyboard,
    _goods_mobile_brands_text,
    _goods_samsung_keyboard,
    _goods_samsung_text,
    _max_keyword_slots,
    _samsung_line_keyboard,
    _samsung_line_pick_text,
    _samsung_models,
    _samsung_series_keyboard,
    _samsung_series_models,
    _samsung_series_text,
    _toggle_models,
)
from handlers.helpers import (
    flush_screen,
    is_admin,
    is_vip_user,
    require_user_cb,
    safe_cb_answer,
)
from logging_setup import log_exception

log = logging.getLogger(__name__)
router = Router()


async def _toggle_catalog_keyword(
    cb: CallbackQuery,
    user: dict,
    chat_id: int,
    catalog: list[str] | tuple[str, ...],
    idx: int,
) -> list[str] | None:
    """Переключает модель в keywords; None если лимит или неверный индекс."""
    if idx < 0 or idx >= len(catalog):
        await safe_cb_answer(cb, "Устройство не найдено", show_alert=True)
        return None
    selected = [k.strip().lower() for k in (user.get("keywords") or []) if k.strip()]
    value = catalog[idx].strip().lower()
    max_kw = _max_keyword_slots(user)
    if value in selected:
        selected.remove(value)
    else:
        if len(selected) >= max_kw:
            await safe_cb_answer(
                cb,
                "Лимит: 5 моделей для обычного пользователя.",
                show_alert=True,
            )
            return None
        selected.append(value)
    user["keywords"] = update_keywords(chat_id, selected)
    return user["keywords"]


async def _on_line_toggle_callback(
    cb: CallbackQuery,
    *,
    prefix: str,
    line_labels: dict[str, str],
    lines_map: dict[str, tuple[str, ...]],
    pick_text: Callable[[str, dict], str],
    line_keyboard: Callable[[dict, str, int], InlineKeyboardMarkup | None],
    log_tag: str,
) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    data = (cb.data or "").strip()
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != prefix:
        await cb.answer("Ошибка", show_alert=True)
        return
    line_slug, action, arg_raw = parts[1], parts[2], parts[3]
    if line_slug not in line_labels or not arg_raw.isdigit():
        await cb.answer("Ошибка", show_alert=True)
        return
    arg = int(arg_raw)

    user = await require_user_cb(cb)
    if user is None:
        return

    models = lines_map.get(line_slug, ())
    screen_text = pick_text(line_slug, user)

    try:
        if action == "x":
            await cb.answer()
            return

        if action == "p":
            kb = line_keyboard(user, line_slug, arg)
            if kb is None:
                await cb.answer("Нет моделей", show_alert=True)
                return
            await flush_screen(cb, screen_text, reply_markup=kb)
            return

        if action == "t":
            if await _toggle_catalog_keyword(cb, user, chat_id, models, arg) is None:
                return
            page = arg // GOODS_PER_PAGE
            kb = line_keyboard(user, line_slug, page)
            if kb is None:
                await cb.answer()
                return
            await flush_screen(
                cb,
                screen_text,
                reply_markup=kb,
                markup_only=True,
                notice="Обновлено",
            )
            return

        await cb.answer("Неизвестное действие", show_alert=True)
    except Exception:
        log_exception(log, "%s error data=%s", log_tag, data)
        await safe_cb_answer(cb, "Не удалось обновить", show_alert=True)


@router.callback_query(lambda c: (c.data or "").startswith("bulk:"))
async def on_bulk_select_callback(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    data = (cb.data or "").strip()
    parts = data.split(":")
    user = await require_user_cb(cb)
    if user is None:
        return
    if not is_vip_user(user):
        await cb.answer("Только для VIP", show_alert=True)
        return

    models: list[str] | tuple[str, ...] = []
    text = _goods_mobile_brands_text()
    markup: InlineKeyboardMarkup | None = _goods_mobile_brands_keyboard(user)

    try:
        if data == "bulk:all":
            models = DEVICE_CATALOG
        elif data == "bulk:apple":
            models = _apple_models()
            text = _goods_apple_lines_text()
            markup = _goods_apple_lines_keyboard(user)
        elif data == "bulk:samsung":
            models = _samsung_models()
            text = _goods_samsung_text()
            markup = _goods_samsung_keyboard(user)
        elif len(parts) == 3 and parts[1] == "ap" and parts[2] in LINE_LABELS:
            line_slug = parts[2]
            models = APPLE_LINES.get(line_slug, ())
            text = _goods_line_pick_text(line_slug, user)
        elif len(parts) == 3 and parts[1] == "ss" and parts[2] in SAMSUNG_SERIES_LABELS:
            series_slug = parts[2]
            models = _samsung_series_models(series_slug)
            kb = _samsung_series_keyboard(series_slug, user)
            if kb is None:
                await cb.answer("Серия не найдена", show_alert=True)
                return
            text = _samsung_series_text(series_slug)
            markup = kb
        elif len(parts) == 3 and parts[1] == "sg" and parts[2] in SAMSUNG_LINE_LABELS:
            line_slug = parts[2]
            models = SAMSUNG_LINES.get(line_slug, ())
            text = _samsung_line_pick_text(line_slug, user)
        else:
            await cb.answer("Неизвестное действие", show_alert=True)
            return

        if not models:
            await cb.answer("Нет моделей для выбора", show_alert=True)
            return

        selected, selected_all = _toggle_models(user, models)
        user["keywords"] = update_keywords(chat_id, selected)

        if data == "bulk:all":
            markup = _goods_mobile_brands_keyboard(user)
        elif data == "bulk:apple":
            markup = _goods_apple_lines_keyboard(user)
        elif data == "bulk:samsung":
            markup = _goods_samsung_keyboard(user)
        elif len(parts) == 3 and parts[1] == "ap" and parts[2] in LINE_LABELS:
            markup = _goods_line_keyboard(user, parts[2], 0)
        elif len(parts) == 3 and parts[1] == "ss" and parts[2] in SAMSUNG_SERIES_LABELS:
            markup = _samsung_series_keyboard(parts[2], user)
        elif len(parts) == 3 and parts[1] == "sg" and parts[2] in SAMSUNG_LINE_LABELS:
            markup = _samsung_line_keyboard(user, parts[2], 0)
        if markup is None:
            await cb.answer("Нет моделей для выбора", show_alert=True)
            return

        action = "Выбрано" if selected_all else "Снято"
        await flush_screen(
            cb,
            text,
            reply_markup=markup,
            markup_only=True,
            notice=f"{action} моделей: {len(models)}",
        )
    except Exception:
        log_exception(log, "bulk error data=%s", data)
        await safe_cb_answer(cb, "Не удалось обновить", show_alert=True)


@router.callback_query(lambda c: (c.data or "").startswith("goods:"))
async def on_goods_callback(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    data = (cb.data or "").strip()
    user = await require_user_cb(cb)
    if user is None:
        return

    try:
        if data in ("goods:h", "goods:m"):
            await flush_screen(
                cb,
                _goods_mobile_brands_text(),
                reply_markup=_goods_mobile_brands_keyboard(user),
            )
            return

        if data == "goods:s":
            await flush_screen(
                cb,
                _goods_samsung_text(),
                reply_markup=_goods_samsung_keyboard(user),
            )
            return

        if data == "goods:a":
            await flush_screen(
                cb,
                _goods_apple_lines_text(),
                reply_markup=_goods_apple_lines_keyboard(user),
            )
            return

        await cb.answer("Неизвестное действие", show_alert=True)
    except Exception:
        log_exception(log, "goods error data=%s", data)
        await safe_cb_answer(cb, "Не удалось обновить", show_alert=True)


@router.callback_query(lambda c: (c.data or "").startswith("sg:"))
async def on_samsung_series_callback(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    user = await require_user_cb(cb)
    if user is None:
        return

    parts = (cb.data or "").strip().split(":")
    series_slug = parts[1] if len(parts) == 2 else ""
    kb = _samsung_series_keyboard(series_slug, user)
    if kb is None:
        await cb.answer("Неизвестная серия", show_alert=True)
        return
    await flush_screen(
        cb,
        _samsung_series_text(series_slug),
        reply_markup=kb,
    )


@router.callback_query(lambda c: (c.data or "").startswith(("gt:", "st:")))
async def on_line_toggle_callback(cb: CallbackQuery) -> None:
    data = (cb.data or "").strip()
    if data.startswith("st:"):
        await _on_line_toggle_callback(
            cb,
            prefix="st",
            line_labels=SAMSUNG_LINE_LABELS,
            lines_map=SAMSUNG_LINES,
            pick_text=_samsung_line_pick_text,
            line_keyboard=_samsung_line_keyboard,
            log_tag="samsung",
        )
    else:
        await _on_line_toggle_callback(
            cb,
            prefix="gt",
            line_labels=LINE_LABELS,
            lines_map=APPLE_LINES,
            pick_text=_goods_line_pick_text,
            line_keyboard=_goods_line_keyboard,
            log_tag="goods_tree",
        )


@router.callback_query(lambda c: (c.data or "") == "kw:done")
async def on_keywords_done(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    user = await require_user_cb(cb)
    if user is None:
        return
    uid = cb.from_user.id if cb.from_user else 0
    await flush_screen(
        cb,
        home_text(user, is_new=False),
        reply_markup=home_keyboard(is_admin=is_admin(uid), user=user),
        notice="Сохранено",
    )
