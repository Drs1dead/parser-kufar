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
from logging_setup import log_exception

log = logging.getLogger(__name__)

PER_PAGE = 8
ADM_USERS_PER_PAGE = 6


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def actor_user_id(msg: Message) -> int:
    if msg.from_user:
        return msg.from_user.id
    return msg.chat.id


def maybe_refresh_username(chat_id: int, from_user) -> None:
    if from_user is None or from_user.id != chat_id:
        return
    update_user_username(chat_id, from_user.username)


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
    """Загружает пользователя; при отсутствии отвечает alert и возвращает None."""
    if cb.message is None:
        await cb.answer()
        return None
    user = get_user(cb.message.chat.id)
    if user is None:
        await cb.answer("Сначала /start", show_alert=True)
        return None
    return user


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
