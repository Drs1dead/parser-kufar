"""Callback-кнопки выбора моделей (goods, bulk, kw, ml, gt, st)."""
import logging

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery

from config import DEVICE_CATALOG
from goods_tree import (
    APPLE_LINES,
    GOODS_PER_PAGE,
    LINE_LABELS,
    SAMSUNG_LINE_LABELS,
    SAMSUNG_LINES,
    SAMSUNG_SERIES_LABELS,
)
from db import get_user, update_keywords
from bot_ui import goods_category_keyboard, goods_category_text, home_keyboard, home_text
from handlers.goods_ui import (
    _apple_models,
    _build_keywords_text,
    _build_model_list_text,
    _goods_apple_lines_keyboard,
    _goods_apple_lines_text,
    _goods_line_keyboard,
    _goods_line_pick_text,
    _goods_mobile_brands_keyboard,
    _goods_mobile_brands_text,
    _goods_samsung_keyboard,
    _goods_samsung_text,
    _is_vip_user,
    _keywords_keyboard,
    _max_keyword_slots,
    _model_list_keyboard,
    _models_for_scope,
    _samsung_line_keyboard,
    _samsung_line_pick_text,
    _samsung_models,
    _samsung_series_keyboard,
    _samsung_series_models,
    _samsung_series_text,
    _toggle_models,
)
from handlers.helpers import PER_PAGE, is_admin, maybe_refresh_username, safe_edit_message
from logging_setup import log_exception

log = logging.getLogger(__name__)
router = Router()

@router.callback_query(lambda c: (c.data or "").startswith("bulk:"))
async def on_bulk_select_callback(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    data = (cb.data or "").strip()
    parts = data.split(":")
    maybe_refresh_username(chat_id, cb.from_user)
    user = get_user(chat_id)
    if user is None:
        await cb.answer("Сначала /start", show_alert=True)
        return
    if not _is_vip_user(user):
        await cb.answer("Только для VIP", show_alert=True)
        return

    models: list[str] | tuple[str, ...] = []
    text = _goods_mobile_brands_text()
    markup = _goods_mobile_brands_keyboard(user)

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
            text = _goods_line_pick_text(line_slug)
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
            text = _samsung_line_pick_text(line_slug)
        else:
            await cb.answer("Неизвестное действие", show_alert=True)
            return

        if not models:
            await cb.answer("Нет моделей для выбора", show_alert=True)
            return

        selected, selected_all = _toggle_models(user, models)
        update_keywords(chat_id, selected)
        updated = get_user(chat_id)
        if updated is None:
            await cb.answer("Сначала /start", show_alert=True)
            return

        if data == "bulk:all":
            markup = _goods_mobile_brands_keyboard(updated)
        elif data == "bulk:apple":
            markup = _goods_apple_lines_keyboard(updated)
        elif data == "bulk:samsung":
            markup = _goods_samsung_keyboard(updated)
        elif len(parts) == 3 and parts[1] == "ap" and parts[2] in LINE_LABELS:
            markup = _goods_line_keyboard(updated, parts[2], 0)
        elif len(parts) == 3 and parts[1] == "ss" and parts[2] in SAMSUNG_SERIES_LABELS:
            markup = _samsung_series_keyboard(parts[2], updated)
        elif len(parts) == 3 and parts[1] == "sg" and parts[2] in SAMSUNG_LINE_LABELS:
            markup = _samsung_line_keyboard(updated, parts[2], 0)
        if markup is None:
            await cb.answer("Нет моделей для выбора", show_alert=True)
            return

        await safe_edit_message(cb, text, reply_markup=markup)
        action = "Выбрано" if selected_all else "Снято"
        await cb.answer(f"{action} моделей: {len(models)}")
    except Exception:
        log_exception(log, "bulk error data=%s", data)
        try:
            await cb.answer("Ошибка", show_alert=True)
        except Exception:
            pass


@router.callback_query(lambda c: (c.data or "").startswith("goods:"))
async def on_goods_callback(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    data = (cb.data or "").strip()
    maybe_refresh_username(chat_id, cb.from_user)
    user = get_user(chat_id)

    if user is None:
        await cb.answer("Сначала /start", show_alert=True)
        return

    try:
        if data == "goods:h":
            await safe_edit_message(
                cb,
                goods_category_text(),
                reply_markup=goods_category_keyboard(),
            )
            await cb.answer()
            return

        if data == "goods:m":
            await safe_edit_message(
                cb,
                _goods_mobile_brands_text(),
                reply_markup=_goods_mobile_brands_keyboard(user),
            )
            await cb.answer()
            return

        if data == "goods:s":
            await safe_edit_message(
                cb,
                _goods_samsung_text(),
                reply_markup=_goods_samsung_keyboard(user),
            )
            await cb.answer()
            return

        if data == "goods:a":
            await safe_edit_message(
                cb,
                _goods_apple_lines_text(),
                reply_markup=_goods_apple_lines_keyboard(user),
            )
            await cb.answer()
            return

        if data == "goods:w":
            await safe_edit_message(
                cb,
                _build_model_list_text(user, "a"),
                reply_markup=_model_list_keyboard(user, "a", page=0),
            )
            await cb.answer()
            return

        if data == "goods:sw":
            await safe_edit_message(
                cb,
                _build_model_list_text(user, "s"),
                reply_markup=_model_list_keyboard(user, "s", page=0),
            )
            await cb.answer()
            return

        if data.startswith("goods:soon:"):
            await cb.answer("Раздел в разработке.", show_alert=True)
            return

        await cb.answer("Неизвестное действие", show_alert=True)
    except Exception:
        log_exception(log, "goods error data=%s", data)
        try:
            await cb.answer("Ошибка", show_alert=True)
        except Exception:
            pass


@router.callback_query(lambda c: (c.data or "").startswith("sg:"))
async def on_samsung_series_callback(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    maybe_refresh_username(chat_id, cb.from_user)
    user = get_user(chat_id)
    if user is None:
        await cb.answer("Сначала /start", show_alert=True)
        return

    parts = (cb.data or "").strip().split(":")
    series_slug = parts[1] if len(parts) == 2 else ""
    kb = _samsung_series_keyboard(series_slug, user)
    if kb is None:
        await cb.answer("Неизвестная серия", show_alert=True)
        return
    await safe_edit_message(
        cb,
        _samsung_series_text(series_slug),
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(lambda c: (c.data or "").startswith("st:"))
async def on_samsung_line_callback(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    data = (cb.data or "").strip()
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "st":
        await cb.answer("Ошибка", show_alert=True)
        return
    line_slug, action, arg_raw = parts[1], parts[2], parts[3]
    if line_slug not in SAMSUNG_LINE_LABELS or not arg_raw.isdigit():
        await cb.answer("Ошибка", show_alert=True)
        return
    arg = int(arg_raw)

    maybe_refresh_username(chat_id, cb.from_user)
    user = get_user(chat_id)
    if user is None:
        await cb.answer("Сначала /start", show_alert=True)
        return

    models = SAMSUNG_LINES.get(line_slug, ())

    try:
        if action == "x":
            await cb.answer()
            return

        if action == "p":
            kb = _samsung_line_keyboard(user, line_slug, arg)
            if kb is None:
                await cb.answer("Нет моделей", show_alert=True)
                return
            await safe_edit_message(
                cb,
                _samsung_line_pick_text(line_slug),
                reply_markup=kb,
            )
            await cb.answer()
            return

        if action == "t":
            idx = arg
            if idx < 0 or idx >= len(models):
                await cb.answer("Неверная модель", show_alert=True)
                return
            value = models[idx].strip().lower()
            selected = [k.strip().lower() for k in (user.get("keywords") or []) if k.strip()]
            max_kw = _max_keyword_slots(user)
            if value in selected:
                selected.remove(value)
            else:
                if len(selected) >= max_kw:
                    await cb.answer(
                        "Лимит: 5 моделей для обычного пользователя.",
                        show_alert=True,
                    )
                    return
                selected.append(value)
            update_keywords(chat_id, selected)
            updated = get_user(chat_id)
            if updated is None:
                await cb.answer("Сначала /start", show_alert=True)
                return
            page = idx // GOODS_PER_PAGE
            kb = _samsung_line_keyboard(updated, line_slug, page)
            if kb is None:
                await cb.answer()
                return
            await safe_edit_message(
                cb,
                _samsung_line_pick_text(line_slug),
                reply_markup=kb,
            )
            await cb.answer("Обновлено")
            return

        await cb.answer("Неизвестное действие", show_alert=True)
    except Exception:
        log_exception(log, "samsung error data=%s", data)
        try:
            await cb.answer("Ошибка", show_alert=True)
        except Exception:
            pass


@router.callback_query(lambda c: (c.data or "").startswith("gt:"))
async def on_goods_line_callback(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    data = (cb.data or "").strip()
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "gt":
        await cb.answer("Ошибка", show_alert=True)
        return
    line_slug, action, arg_raw = parts[1], parts[2], parts[3]
    if line_slug not in LINE_LABELS:
        await cb.answer("Ошибка", show_alert=True)
        return
    if not arg_raw.isdigit():
        await cb.answer("Ошибка", show_alert=True)
        return
    arg = int(arg_raw)

    maybe_refresh_username(chat_id, cb.from_user)
    user = get_user(chat_id)
    if user is None:
        await cb.answer("Сначала /start", show_alert=True)
        return

    models = APPLE_LINES.get(line_slug, ())

    try:
        if action == "x":
            await cb.answer()
            return

        if action == "p":
            page = arg
            kb = _goods_line_keyboard(user, line_slug, page)
            if kb is None:
                await cb.answer("Нет моделей", show_alert=True)
                return
            await safe_edit_message(
                cb,
                _goods_line_pick_text(line_slug),
                reply_markup=kb,
            )
            await cb.answer()
            return

        if action == "t":
            idx = arg
            if idx < 0 or idx >= len(models):
                await cb.answer("Неверная модель", show_alert=True)
                return
            value = models[idx].strip().lower()
            selected = [k.strip().lower() for k in (user.get("keywords") or []) if k.strip()]
            max_kw = _max_keyword_slots(user)
            if value in selected:
                selected.remove(value)
            else:
                if len(selected) >= max_kw:
                    await cb.answer(
                        "Лимит: 5 моделей для обычного пользователя.",
                        show_alert=True,
                    )
                    return
                selected.append(value)
            update_keywords(chat_id, selected)
            updated = get_user(chat_id)
            if updated is None:
                await cb.answer("Сначала /start", show_alert=True)
                return
            page = idx // GOODS_PER_PAGE
            kb = _goods_line_keyboard(updated, line_slug, page)
            if kb is None:
                await cb.answer()
                return
            await safe_edit_message(
                cb,
                _goods_line_pick_text(line_slug),
                reply_markup=kb,
            )
            await cb.answer("Обновлено")
            return

        await cb.answer("Неизвестное действие", show_alert=True)
    except Exception:
        log_exception(log, "goods_tree error data=%s", data)
        try:
            await cb.answer("Ошибка", show_alert=True)
        except Exception:
            pass


@router.callback_query(lambda c: (c.data or "").startswith("ml:"))
async def on_model_list_callback(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    data = (cb.data or "").strip()
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "ml" or parts[1] not in ("a", "s", "all"):
        await cb.answer("Ошибка", show_alert=True)
        return
    scope, action, arg_raw = parts[1], parts[2], parts[3]
    if not arg_raw.isdigit():
        await cb.answer("Ошибка", show_alert=True)
        return
    arg = int(arg_raw)

    maybe_refresh_username(chat_id, cb.from_user)
    user = get_user(chat_id)
    if user is None:
        await cb.answer("Сначала /start", show_alert=True)
        return

    models = _models_for_scope(scope)

    try:
        if action == "x":
            await cb.answer()
            return

        if action == "p":
            await safe_edit_message(
                cb,
                _build_model_list_text(user, scope),
                reply_markup=_model_list_keyboard(user, scope, page=arg),
            )
            await cb.answer()
            return

        if action == "t":
            idx = arg
            if idx < 0 or idx >= len(models):
                await cb.answer("Устройство не найдено", show_alert=True)
                return
            selected = [k.strip().lower() for k in (user.get("keywords") or []) if k.strip()]
            value = models[idx].strip().lower()
            max_kw = _max_keyword_slots(user)
            if value in selected:
                selected.remove(value)
            else:
                if len(selected) >= max_kw:
                    await cb.answer(
                        "Лимит: 5 моделей для обычного пользователя.",
                        show_alert=True,
                    )
                    return
                selected.append(value)
            update_keywords(chat_id, selected)
            updated = get_user(chat_id)
            if updated is None:
                await cb.answer("Сначала /start", show_alert=True)
                return
            page = idx // PER_PAGE
            await safe_edit_message(
                cb,
                _build_model_list_text(updated, scope),
                reply_markup=_model_list_keyboard(updated, scope, page=page),
            )
            await cb.answer("Обновлено")
            return

        await cb.answer("Неизвестное действие", show_alert=True)
    except Exception:
        log_exception(log, "model_list error data=%s", data)
        try:
            await cb.answer("Ошибка", show_alert=True)
        except Exception:
            pass


@router.callback_query(lambda c: (c.data or "") == "kw:x")
async def on_keywords_nav_noop(cb: CallbackQuery) -> None:
    await cb.answer()


@router.callback_query(lambda c: (c.data or "").startswith("kw:page:"))
async def on_keywords_page(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    maybe_refresh_username(chat_id, cb.from_user)
    user = get_user(chat_id)
    if user is None:
        await cb.answer("Сначала /start", show_alert=True)
        return
    page_raw = (cb.data or "").split(":")[-1]
    page = int(page_raw) if page_raw.isdigit() else 0
    await safe_edit_message(
        cb,
        _build_keywords_text(user),
        reply_markup=_keywords_keyboard(user, page=page),
    )
    await cb.answer()


@router.callback_query(lambda c: (c.data or "").startswith("kw:toggle:"))
async def on_keywords_toggle(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    maybe_refresh_username(chat_id, cb.from_user)
    user = get_user(chat_id)
    if user is None:
        await cb.answer("Сначала /start", show_alert=True)
        return

    idx_raw = (cb.data or "").split(":")[-1]
    if not idx_raw.isdigit():
        await cb.answer("Ошибка выбора", show_alert=True)
        return
    idx = int(idx_raw)
    if idx < 0 or idx >= len(DEVICE_CATALOG):
        await cb.answer("Устройство не найдено", show_alert=True)
        return

    selected = [k.strip().lower() for k in (user.get("keywords") or []) if k.strip()]
    value = DEVICE_CATALOG[idx].strip().lower()
    max_kw = _max_keyword_slots(user)
    if value in selected:
        selected.remove(value)
    else:
        if len(selected) >= max_kw:
            await cb.answer(
                "Лимит: 5 моделей для обычного пользователя.",
                show_alert=True,
            )
            return
        selected.append(value)

    update_keywords(cb.message.chat.id, selected)
    updated = get_user(cb.message.chat.id)
    if updated is None:
        await cb.answer("Сначала /start", show_alert=True)
        return
    page = idx // PER_PAGE
    await safe_edit_message(
        cb,
        _build_keywords_text(updated),
        reply_markup=_keywords_keyboard(updated, page=page),
    )
    await cb.answer("Обновлено")


@router.callback_query(lambda c: (c.data or "") == "kw:done")
async def on_keywords_done(cb: CallbackQuery) -> None:
    if cb.message is None:
        await cb.answer()
        return
    chat_id = cb.message.chat.id
    maybe_refresh_username(chat_id, cb.from_user)
    user = get_user(chat_id)
    uid = cb.from_user.id if cb.from_user else 0
    if user is None:
        await cb.answer("Сначала /start", show_alert=True)
        return
    selected = user.get("keywords") or []
    await safe_edit_message(
        cb,
        home_text(user, is_new=False)
        + "\n\n✅ <b>Товары сохранены.</b> Выбрано: "
        + str(len(selected))
        + (f"\n<code>{', '.join(selected)}</code>" if selected else ""),
        reply_markup=home_keyboard(is_admin=is_admin(uid), user=user),
    )
    await cb.answer("Сохранено")
