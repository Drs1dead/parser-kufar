"""Админ-панель: статистика, пользователи, VIP, промокоды."""
import logging
import secrets
import string
from html import escape

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from db import (
    clear_market_prices,
    count_users_active,
    count_users_total,
    count_users_vip,
    create_promo_code,
    delete_promo_code,
    delete_user_completely,
    find_users_by_username,
    get_user,
    list_active_promo_codes,
    list_users_page,
    revoke_vip,
    set_vip,
)
from handlers.helpers import (
    ADM_USERS_PER_PAGE,
    actor_user_id,
    format_user_status_html,
    is_admin,
    safe_cb_answer,
    safe_edit_message,
)
from handlers.states import AdminPromoState, AdminUserSearchState, AdminVipGrantState
from logging_setup import log_exception

log = logging.getLogger(__name__)
admin_router = Router()


def admin_home_text() -> str:
    return (
        "🔐 <b>Админ</b>\n\n"
        "📊 статистика · 👥 пользователи · 🎟 промокоды\n"
        "🧹 сброс цен рынка для VIP"
    )


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="adm:st"),
                InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:us:0"),
            ],
            [
                InlineKeyboardButton(
                    text="🧹 Сбросить глобальные цены рынка",
                    callback_data="adm:mp",
                ),
            ],
            [InlineKeyboardButton(text="🎟 Добавить промокод", callback_data="adm:promo")],
            [InlineKeyboardButton(text="🔄 Обновить панель", callback_data="adm:h")],
            [InlineKeyboardButton(text="👤 К меню бота", callback_data="nav:home")],
        ]
    )


def _admin_stats_text() -> str:
    total = count_users_total()
    active = count_users_active()
    vips = count_users_vip()
    return (
        "📊 <b>Статистика</b>\n\n"
        f"Всего пользователей в базе: <b>{total}</b>\n"
        f"С активной подпиской: <b>{active}</b>\n"
        f"С действующим VIP: <b>{vips}</b>"
    )


def _admin_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="adm:h")],
        ]
    )


def _admin_users_page_text(page: int) -> str:
    total = count_users_total()
    if total == 0:
        return "👥 <b>Пользователи</b>\n\nБаза пуста."
    pages = max(1, (total + ADM_USERS_PER_PAGE - 1) // ADM_USERS_PER_PAGE)
    page = max(0, min(page, pages - 1))
    return (
        "👥 <b>Пользователи</b>\n\n"
        f"Стр. <b>{page + 1}</b> / <b>{pages}</b> · всего <b>{total}</b>\n\n"
        "Нажмите на строку — карточка\n"
        "🔍 <b>Поиск</b> — по @username"
    )


def _admin_users_keyboard(page: int) -> InlineKeyboardMarkup:
    total = count_users_total()
    rows: list[list[InlineKeyboardButton]] = []
    if total == 0:
        rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:h")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    pages = max(1, (total + ADM_USERS_PER_PAGE - 1) // ADM_USERS_PER_PAGE)
    page = max(0, min(page, pages - 1))
    offset = page * ADM_USERS_PER_PAGE
    chunk = list_users_page(offset=offset, limit=ADM_USERS_PER_PAGE)

    for u in chunk:
        cid = u["chat_id"]
        role_icon = "⭐" if u.get("role") == "vip" else "·"
        act = "✅" if u.get("active") else "⏸"
        n_kw = len(u.get("keywords") or [])
        un = (u.get("username") or "").strip()
        suffix = f" · {n_kw} устр."
        prefix = f"{act}{role_icon} "
        if un:
            room = 58 - len(prefix) - len(suffix)
            if room >= 4:
                handle = f"@{un}" if len(un) + 1 <= room else f"@{un[: max(1, room - 2)]}…"
            else:
                handle = str(cid)
        else:
            handle = str(cid)
        label = prefix + handle + suffix
        if len(label) > 58:
            label = f"{prefix}{cid}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"adm:u:{cid}")])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm:us:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="adm:x"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"adm:us:{page + 1}"))
    rows.append(nav)
    rows.append(
        [InlineKeyboardButton(text="🔍 Поиск @username", callback_data="adm:us:find")]
    )
    rows.append([InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="adm:h")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _admin_user_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ Выдать VIP", callback_data=f"adm:vg:{chat_id}"),
                InlineKeyboardButton(text="⛔ Снять VIP", callback_data=f"adm:unv:{chat_id}"),
            ],
            [InlineKeyboardButton(text="🗑 Удалить из БД", callback_data=f"adm:del:{chat_id}")],
            [
                InlineKeyboardButton(text="⬅️ К списку", callback_data="adm:us:0"),
                InlineKeyboardButton(text="🏠 Админ", callback_data="adm:h"),
            ],
        ]
    )


def _admin_delete_confirm_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Удалить навсегда",
                    callback_data=f"adm:del:yes:{chat_id}",
                ),
                InlineKeyboardButton(text="Отмена", callback_data=f"adm:u:{chat_id}"),
            ],
        ]
    )


def _admin_delete_confirm_text(chat_id: int) -> str:
    return (
        f"🗑 <b>Удалить пользователя {chat_id}?</b>\n\n"
        "Из базы исчезнут настройки, история просмотров и привязки.\n"
        "Действие <b>необратимо</b>."
    )


def _admin_market_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, очистить", callback_data="adm:mp:go"),
                InlineKeyboardButton(text="Отмена", callback_data="adm:h"),
            ],
        ]
    )


def _admin_promos_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список промокодов", callback_data="adm:promo:list")],
            [
                InlineKeyboardButton(text="🎲 Создать пачку", callback_data="adm:promo:random"),
                InlineKeyboardButton(text="✍️ Создать один", callback_data="adm:promo:manual"),
            ],
            [InlineKeyboardButton(text="🗑 Удалить промокод", callback_data="adm:promo:del")],
            [InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="adm:h")],
        ]
    )


def _admin_promos_text() -> str:
    return "🎟 <b>Промокоды</b>\n\nСоздание и удаление."


def _promo_codes_list_text() -> str:
    promos = list_active_promo_codes()
    if not promos:
        return "🎟 <b>Промокоды</b>\n\nСписок пуст."
    lines = ["🎟 <b>Активные промокоды</b>", ""]
    for p in promos:
        max_uses = int(p.get("max_uses") or 0)
        uses = int(p.get("uses") or 0)
        limit = "∞" if max_uses <= 0 else f"{uses}/{max_uses}"
        lines.append(
            f"<code>{escape(str(p.get('code') or ''))}</code> · "
            f"{int(p.get('vip_days') or 0)} дн. · {limit}"
        )
    lines.append("")
    lines.append("<i>Удалить — кнопка 🗑 под кодом.</i>")
    return "\n".join(lines)


def _promo_codes_list_keyboard() -> InlineKeyboardMarkup:
    promos = list_active_promo_codes()
    rows: list[list[InlineKeyboardButton]] = []
    for i, p in enumerate(promos[:20]):
        code = str(p.get("code") or "")
        label = f"🗑 {code}" if len(code) <= 28 else f"🗑 {code[:26]}…"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"adm:px:{i}")]
        )
    rows.append([InlineKeyboardButton(text="⬅️ К промокодам", callback_data="adm:promo")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_admin_user_card(
    cb: CallbackQuery, target_id: int, user: dict | None = None
) -> None:
    u = user if user is not None else get_user(target_id)
    if u is None:
        await cb.answer("Не найден", show_alert=True)
        return
    card = await format_user_status_html(cb.bot, u)
    await safe_edit_message(
        cb,
        card,
        reply_markup=_admin_user_keyboard(target_id),
    )


def _generate_promo_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))
@admin_router.callback_query(lambda c: (c.data or "").startswith("adm:"))
async def on_admin_callback(cb: CallbackQuery, state: FSMContext) -> None:
    uid = cb.from_user.id if cb.from_user else 0
    if not is_admin(uid):
        await cb.answer("Нет доступа", show_alert=True)
        return
    if cb.message is None:
        await cb.answer()
        return

    data = (cb.data or "").strip()
    parts = data.split(":")

    try:
        if data == "adm:h":
            await state.clear()
            await safe_edit_message(
                cb,
                admin_home_text(),
                reply_markup=admin_main_keyboard(),
            )
            await cb.answer()
            return

        if data == "adm:x":
            await cb.answer()
            return

        if data == "adm:st":
            await safe_edit_message(
                cb,
                _admin_stats_text(),
                reply_markup=_admin_stats_keyboard(),
            )
            await cb.answer()
            return

        if data == "adm:promo":
            await state.clear()
            await safe_edit_message(
                cb,
                _admin_promos_text(),
                reply_markup=_admin_promos_keyboard(),
            )
            await cb.answer()
            return

        if data == "adm:promo:list":
            await state.clear()
            await safe_edit_message(
                cb,
                _promo_codes_list_text(),
                reply_markup=_promo_codes_list_keyboard(),
            )
            await cb.answer()
            return

        if data == "adm:promo:del":
            await state.set_state(AdminPromoState.waiting_delete)
            await safe_edit_message(
                cb,
                "🗑 <b>Удалить промокод</b>\n\n"
                "Введите код — удалится из базы навсегда (и активации).",
                reply_markup=_admin_promos_keyboard(),
            )
            await cb.answer()
            return

        if data == "adm:promo:random":
            await state.set_state(AdminPromoState.waiting_random)
            await safe_edit_message(
                cb,
                "🎲 <b>Случайные промокоды</b>\n\n"
                "Введите количество промокодов и срок VIP в днях через пробел.\n"
                "Пример: <code>5 7</code>",
                reply_markup=_admin_promos_keyboard(),
            )
            await cb.answer()
            return

        if data == "adm:promo:manual":
            await state.set_state(AdminPromoState.waiting_manual)
            await safe_edit_message(
                cb,
                "✍️ <b>Промокод вручную</b>\n\n"
                "Введите название, количество использований и срок VIP в днях через пробел.\n"
                "Пример: <code>SALE2026 10 7</code>",
                reply_markup=_admin_promos_keyboard(),
            )
            await cb.answer()
            return

        if data == "adm:us:find":
            await state.set_state(AdminUserSearchState.waiting_username)
            await safe_edit_message(
                cb,
                "🔍 <b>Поиск пользователя</b>\n\n"
                "Введите @username или имя без @.\n"
                "Пример: <code>Quantix_code</code>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="adm:us:0")],
                    ]
                ),
            )
            await cb.answer()
            return

        if len(parts) == 3 and parts[0] == "adm" and parts[1] == "us" and parts[2].isdigit():
            page = int(parts[2])
            await state.clear()
            await safe_edit_message(
                cb,
                _admin_users_page_text(page),
                reply_markup=_admin_users_keyboard(page),
            )
            await cb.answer()
            return

        if len(parts) == 3 and parts[0] == "adm" and parts[1] == "u" and parts[2].lstrip("-").isdigit():
            target_id = int(parts[2])
            u = get_user(target_id)
            if u is None:
                await cb.answer("Пользователь не найден", show_alert=True)
                return
            await _show_admin_user_card(cb, target_id, user=u)
            await cb.answer()
            return

        if len(parts) == 3 and parts[0] == "adm" and parts[1] == "vg" and parts[2].lstrip("-").isdigit():
            target_id = int(parts[2])
            if get_user(target_id) is None:
                await cb.answer("Пользователь не найден", show_alert=True)
                return
            await state.set_state(AdminVipGrantState.waiting_days)
            await state.update_data(vip_target_id=target_id)
            await safe_edit_message(
                cb,
                f"⭐ <b>VIP для {target_id}</b>\n\n"
                "Введите число дней одним сообщением.\n"
                "Пример: <code>30</code>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="⬅️ Отмена",
                                callback_data=f"adm:u:{target_id}",
                            )
                        ],
                    ]
                ),
            )
            await cb.answer()
            return

        if (
            len(parts) == 4
            and parts[0] == "adm"
            and parts[1] == "del"
            and parts[2] == "yes"
            and parts[3].lstrip("-").isdigit()
        ):
            target_id = int(parts[3])
            if not delete_user_completely(target_id):
                await cb.answer("Уже удалён", show_alert=True)
                return
            await state.clear()
            await safe_edit_message(
                cb,
                f"✅ Пользователь <b>{target_id}</b> удалён из базы.",
                reply_markup=_admin_users_keyboard(0),
            )
            await cb.answer("Удалено")
            return

        if len(parts) == 3 and parts[0] == "adm" and parts[1] == "del" and parts[2].lstrip("-").isdigit():
            target_id = int(parts[2])
            if get_user(target_id) is None:
                await cb.answer("Пользователь не найден", show_alert=True)
                return
            await safe_edit_message(
                cb,
                _admin_delete_confirm_text(target_id),
                reply_markup=_admin_delete_confirm_keyboard(target_id),
            )
            await cb.answer()
            return

        if len(parts) == 3 and parts[0] == "adm" and parts[1] == "px" and parts[2].isdigit():
            promos = list_active_promo_codes()
            idx = int(parts[2])
            if idx < 0 or idx >= len(promos):
                await cb.answer("Промокод не найден", show_alert=True)
                return
            code = str(promos[idx].get("code") or "")
            if delete_promo_code(code):
                await safe_edit_message(
                    cb,
                    _promo_codes_list_text(),
                    reply_markup=_promo_codes_list_keyboard(),
                )
                await cb.answer(f"🗑 {code}")
            else:
                await cb.answer("Не удалось удалить", show_alert=True)
            return

        if len(parts) == 3 and parts[0] == "adm" and parts[1] == "unv" and parts[2].lstrip("-").isdigit():
            target_id = int(parts[2])
            u = get_user(target_id)
            if u is None:
                await cb.answer("Пользователь не найден", show_alert=True)
                return
            revoke_vip(target_id)
            u = get_user(target_id)
            await _show_admin_user_card(cb, target_id, user=u)
            await cb.answer("VIP снят")
            return

        if data == "adm:mp:go":
            n = clear_market_prices()
            await safe_edit_message(
                cb,
                f"✅ Готово. Удалено записей о ценах: <b>{n}</b>\n\n" + admin_home_text(),
                reply_markup=admin_main_keyboard(),
            )
            await cb.answer("Сброшено")
            return

        if data == "adm:mp":
            await safe_edit_message(
                cb,
                "🧹 <b>Сброс глобальных цен рынка</b>\n\n"
                "Будут удалены записи из <code>market_prices</code> "
                "(средняя цена для VIP начнёт накапливаться заново).\n\n"
                "Подтверди действие:",
                reply_markup=_admin_market_confirm_keyboard(),
            )
            await cb.answer()
            return

        await cb.answer("Неизвестное действие", show_alert=True)
    except Exception:
        log_exception(log, "admin error data=%s", data)
        await safe_cb_answer(cb, "Не удалось выполнить", show_alert=True)


@admin_router.message(AdminPromoState.waiting_random, F.text, ~F.text.startswith("/"))
async def on_admin_random_promos_text(msg: Message, state: FSMContext) -> None:
    uid = actor_user_id(msg)
    if not is_admin(uid):
        await state.clear()
        return

    parts = (msg.text or "").strip().split()
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        await msg.answer(
            "Введите два числа через пробел: количество промокодов и срок VIP в днях.\n"
            "Пример: <code>5 7</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    count = int(parts[0])
    days = int(parts[1])
    if not 1 <= count <= 100 or not 1 <= days <= 3650:
        await msg.answer(
            "Количество должно быть от 1 до 100, срок VIP — от 1 до 3650 дней.",
            parse_mode=ParseMode.HTML,
        )
        return

    created: list[str] = []
    attempts = 0
    while len(created) < count and attempts < count * 10:
        attempts += 1
        code = _generate_promo_code()
        if create_promo_code(code, vip_days=days, max_uses=1):
            created.append(code)

    if len(created) != count:
        await msg.answer("Не удалось создать нужное количество промокодов. Попробуйте ещё раз.")
        return

    await state.clear()
    await msg.answer(
        f"✅ Создано промокодов: <b>{len(created)}</b>",
        parse_mode=ParseMode.HTML,
    )
    await msg.answer(
        _promo_codes_list_text(),
        reply_markup=_promo_codes_list_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@admin_router.message(AdminPromoState.waiting_manual, F.text, ~F.text.startswith("/"))
async def on_admin_manual_promo_text(msg: Message, state: FSMContext) -> None:
    uid = actor_user_id(msg)
    if not is_admin(uid):
        await state.clear()
        return

    parts = (msg.text or "").strip().split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await msg.answer(
            "Введите название, количество использований и срок VIP в днях через пробел.\n"
            "Пример: <code>SALE2026 10 7</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    code = parts[0]
    max_uses = int(parts[1])
    days = int(parts[2])
    if not 1 <= max_uses <= 1_000_000 or not 1 <= days <= 3650:
        await msg.answer(
            "Количество использований должно быть от 1, срок VIP — от 1 до 3650 дней.",
            parse_mode=ParseMode.HTML,
        )
        return

    if not create_promo_code(code, vip_days=days, max_uses=max_uses):
        await msg.answer(
            "Такой промокод уже существует или название пустое. Введите данные заново.",
            parse_mode=ParseMode.HTML,
        )
        return

    await state.clear()
    await msg.answer(
        f"✅ Промокод <code>{escape(code)}</code> создан",
        parse_mode=ParseMode.HTML,
    )
    await msg.answer(
        _promo_codes_list_text(),
        reply_markup=_promo_codes_list_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@admin_router.message(AdminPromoState.waiting_delete, F.text, ~F.text.startswith("/"))
async def on_admin_promo_delete_text(msg: Message, state: FSMContext) -> None:
    uid = actor_user_id(msg)
    if not is_admin(uid):
        await state.clear()
        return
    code = (msg.text or "").strip()
    if delete_promo_code(code):
        await state.clear()
        await msg.answer(
            f"🗑 Промокод <code>{escape(code.strip().upper())}</code> удалён",
            parse_mode=ParseMode.HTML,
        )
        await msg.answer(
            _promo_codes_list_text(),
            reply_markup=_promo_codes_list_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    else:
        await msg.answer(
            "Промокод не найден. Проверьте написание и попробуйте снова.",
            parse_mode=ParseMode.HTML,
        )


@admin_router.message(AdminUserSearchState.waiting_username, F.text, ~F.text.startswith("/"))
async def on_admin_user_search_text(msg: Message, state: FSMContext) -> None:
    uid = actor_user_id(msg)
    if not is_admin(uid):
        await state.clear()
        return
    query = (msg.text or "").strip().lstrip("@")
    if not query:
        await msg.answer("Введите username.", parse_mode=ParseMode.HTML)
        return
    users = find_users_by_username(query)
    await state.clear()
    if not users:
        await msg.answer(
            f"По запросу <code>@{escape(query)}</code> никого нет в базе.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ К списку", callback_data="adm:us:0")],
                ]
            ),
            parse_mode=ParseMode.HTML,
        )
        return
    if len(users) == 1:
        u = users[0]
        target_id = int(u["chat_id"])
        card = await format_user_status_html(msg.bot, u)
        await msg.answer(
            card,
            reply_markup=_admin_user_keyboard(target_id),
            parse_mode=ParseMode.HTML,
        )
        return
    rows: list[list[InlineKeyboardButton]] = []
    for u in users[:10]:
        cid = int(u["chat_id"])
        un = (u.get("username") or "").strip()
        label = f"@{un}" if un else str(cid)
        if len(label) > 40:
            label = label[:38] + "…"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"adm:u:{cid}")]
        )
    rows.append([InlineKeyboardButton(text="⬅️ К списку", callback_data="adm:us:0")])
    await msg.answer(
        f"🔍 Найдено <b>{len(users)}</b> по <code>@{escape(query)}</code>:\n"
        "Выберите пользователя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode=ParseMode.HTML,
    )


@admin_router.message(AdminVipGrantState.waiting_days, F.text, ~F.text.startswith("/"))
async def on_admin_vip_grant_days(msg: Message, state: FSMContext) -> None:
    uid = actor_user_id(msg)
    if not is_admin(uid):
        await state.clear()
        return
    raw = (msg.text or "").strip()
    if not raw.isdigit():
        await msg.answer("Введите число дней, например <code>30</code>.", parse_mode=ParseMode.HTML)
        return
    days = int(raw)
    if not 1 <= days <= 3650:
        await msg.answer("От 1 до 3650 дней.", parse_mode=ParseMode.HTML)
        return
    data = await state.get_data()
    target_id = data.get("vip_target_id")
    if target_id is None:
        await state.clear()
        await msg.answer("Сессия сброшена. Откройте карточку пользователя снова.")
        return
    target_id = int(target_id)
    u = get_user(target_id)
    if u is None:
        await state.clear()
        await msg.answer("Пользователь не найден.")
        return
    set_vip(target_id, days=days)
    await state.clear()
    u = get_user(target_id)
    if u is None:
        await msg.answer("Ошибка сохранения.")
        return
    card = await format_user_status_html(msg.bot, u)
    await msg.answer(
        f"✅ VIP на <b>{days}</b> дн.",
        parse_mode=ParseMode.HTML,
    )
    await msg.answer(
        card,
        reply_markup=_admin_user_keyboard(target_id),
        parse_mode=ParseMode.HTML,
    )
