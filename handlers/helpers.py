"""Общие хелперы Telegram-хендлеров."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from config import ADMIN_IDS
from db import get_user, update_user_username
from formatter import format_status
from goods_tree import GOODS_PER_PAGE
from logging_setup import log_exception

log = logging.getLogger(__name__)

PER_PAGE = GOODS_PER_PAGE
ADM_USERS_PER_PAGE = 6


def is_vip_user(user: dict | None) -> bool:
    return bool(user and user.get("role") == "vip")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def actor_user_id(msg: Message) -> int:
    if msg.from_user:
        return msg.from_user.id
    return msg.chat.id


def _norm_tg_username(username: str | None) -> str:
    if not username:
        return ""
    return username.strip().lstrip("@")[:64]


def sync_username_from_message(user: dict, msg: Message) -> None:
    if msg.from_user is None or msg.from_user.id != msg.chat.id:
        return
    new = _norm_tg_username(msg.from_user.username)
    if new == (user.get("username") or ""):
        return
    update_user_username(msg.chat.id, msg.from_user.username)
    user["username"] = new


def sync_username_from_callback(user: dict, cb: CallbackQuery) -> None:
    if cb.message is None or cb.from_user is None:
        return
    chat_id = cb.message.chat.id
    if cb.from_user.id != chat_id:
        return
    new = _norm_tg_username(cb.from_user.username)
    if new == (user.get("username") or ""):
        return
    update_user_username(chat_id, cb.from_user.username)
    user["username"] = new


def load_user_from_message(msg: Message) -> dict | None:
    user = get_user(msg.chat.id)
    if user is None:
        return None
    sync_username_from_message(user, msg)
    return user


async def enrich_username_from_get_chat(bot: Bot, user: dict) -> None:
    if (user.get("username") or "").strip():
        return
    chat_id = user.get("chat_id")
    if chat_id is None:
        return
    try:
        chat = await bot.get_chat(chat_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        return
    un = (getattr(chat, "username", None) or "").strip()
    if not un:
        return
    user["username"] = un
    update_user_username(int(chat_id), un)


async def format_user_status_html(bot: Bot, user: dict) -> str:
    await enrich_username_from_get_chat(bot, user)
    return format_status(user)


async def require_user_cb(cb: CallbackQuery) -> dict | None:
    if cb.message is None:
        await safe_cb_answer(cb)
        return None
    user = get_user(cb.message.chat.id)
    if user is None:
        await safe_cb_answer(cb, "Сначала /start", show_alert=True)
        return None
    sync_username_from_callback(user, cb)
    return user


async def safe_cb_answer(
    cb: CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> None:
    """Ответ на callback; без text — только снять «часики» (не передавать '')."""
    try:
        if text:
            await cb.answer(text, show_alert=show_alert)
        else:
            await cb.answer()
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "query is too old" in err or "query id is invalid" in err:
            return
        if "query has already been answered" in err or "already been answered" in err:
            return
        log.debug("cb.answer bad_request: %s", e)


async def safe_edit_message(
    cb: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if cb.message is None:
        return
    try:
        await cb.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err or "not modified" in err:
            return
        log.debug("edit bad_request: %s", e)
    except Exception as e:
        log_exception(log, "edit failed: %s", e)


async def safe_edit_reply_markup(
    cb: CallbackQuery,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    if cb.message is None:
        return
    try:
        await cb.message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err or "not modified" in err:
            return
        log.debug("edit_markup bad_request: %s", e)
    except Exception as e:
        log_exception(log, "edit_markup failed: %s", e)


async def flush_screen(
    cb: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    notice: str | None = None,
    markup_only: bool = False,
    show_alert: bool = False,
    answer: bool = True,
) -> None:
    """Снять «часики» и обновить экран (сначала answer, затем edit)."""
    if answer:
        await safe_cb_answer(cb, notice, show_alert=show_alert)
    if markup_only:
        await safe_edit_reply_markup(cb, reply_markup)
        return
    await safe_edit_message(cb, text, reply_markup=reply_markup)
