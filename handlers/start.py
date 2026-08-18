"""Старт, рефералка."""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import REFERRAL_VIP_DAYS_PER_FRIEND
from db import add_user, get_user, process_referral_signup
from bot_ui import home_keyboard, home_text
from handlers.helpers import actor_user_id, is_admin

log = logging.getLogger(__name__)
router = Router()


def extract_referral_code(text: str | None) -> str | None:
    if not text:
        return None
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    payload = parts[1].strip()
    if payload.lower().startswith("ref_"):
        return payload[4:].strip()
    return None


async def present_home(
    msg: Message,
    state: FSMContext,
    *,
    bot: Bot | None = None,
) -> None:
    """Главное меню: регистрация при первом обращении и показ home."""
    await state.clear()
    chat_id = msg.chat.id
    un = msg.from_user.username if msg.from_user else None
    is_new = add_user(chat_id, username=un)
    if is_new:
        ref_code = extract_referral_code(msg.text)
        referrer_id = (
            process_referral_signup(chat_id, ref_code) if ref_code else None
        )
        if referrer_id is not None and bot is not None:
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎁 <b>+{REFERRAL_VIP_DAYS_PER_FRIEND} дн. VIP</b> — "
                    "новый пользователь перешёл по вашей ссылке.",
                    parse_mode=ParseMode.HTML,
                )
            except TelegramForbiddenError:
                pass
    user = get_user(chat_id)
    uid = actor_user_id(msg)
    await msg.answer(
        home_text(user, is_new=is_new),
        reply_markup=home_keyboard(is_admin=is_admin(uid), user=user),
        parse_mode=ParseMode.HTML,
    )


@router.message(CommandStart())
async def on_start(msg: Message, state: FSMContext, bot: Bot) -> None:
    log.debug("start chat_id=%s", msg.chat.id)
    await present_home(msg, state, bot=bot)


@router.message(F.text, ~F.text.startswith("/"), StateFilter(None))
async def on_any_text(msg: Message, state: FSMContext, bot: Bot) -> None:
    """Любой текст вне FSM → главное меню (удобнее, чем молчание)."""
    await present_home(msg, state, bot=bot)
