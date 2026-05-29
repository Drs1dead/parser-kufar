"""Старт, рефералка, ответ на любой текст."""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import REFERRAL_VIP_DAYS_PER_FRIEND
from db import add_user, get_user, process_referral_signup
from bot_ui import home_keyboard, home_text
from handlers.helpers import actor_user_id, is_admin, maybe_refresh_username
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
    msg: Message, state: FSMContext, *, register: bool, bot: Bot | None = None
) -> None:
    """Главное меню — то же, что /start (и для любого текста в чат)."""
    await state.clear()
    chat_id = msg.chat.id
    un = msg.from_user.username if msg.from_user else None
    is_new = add_user(chat_id, username=un) if register else False
    if register and is_new:
        ref_code = extract_referral_code(msg.text)
        if ref_code and process_referral_signup(chat_id, ref_code) and bot is not None:
            referrer = get_user(chat_id)
            if referrer and referrer.get("referred_by"):
                rid = int(referrer["referred_by"])
                try:
                    await bot.send_message(
                        rid,
                        f"🎁 <b>+{REFERRAL_VIP_DAYS_PER_FRIEND} дн. VIP</b> — "
                        "новый пользователь перешёл по вашей ссылке.",
                        parse_mode=ParseMode.HTML,
                    )
                except TelegramForbiddenError:
                    pass
    if not register:
        maybe_refresh_username(chat_id, msg.from_user)
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
    await present_home(msg, state, register=True, bot=bot)


@router.message(F.text)
async def on_any_text(msg: Message, state: FSMContext, bot: Bot) -> None:
    await present_home(
        msg, state, register=get_user(msg.chat.id) is None, bot=bot
    )
