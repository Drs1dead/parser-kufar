import asyncio
import logging
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import bot_ui
import handlers
from config import (
    CHECK_INTERVAL,
    REGULAR_CHECK_INTERVAL,
    SQLITE_SYNCHRONOUS,
    TOKEN,
    VIP_CHECK_INTERVAL,
)
from db import SQLITE_PATH, close as db_close, init_db
from logging_setup import configure_logging
from poller import poller

log = logging.getLogger("kufar_bot")


async def main() -> None:
    configure_logging()

    if not TOKEN:
        log.error("TOKEN missing in .env")
        sys.exit(1)

    init_db()

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.get_me()
    bot_ui.BOT_USERNAME = (me.username or "").strip()
    if not bot_ui.BOT_USERNAME:
        log.warning("bot has no @username — referral links disabled")

    dp = Dispatcher()
    dp.include_router(handlers.router)

    def _schedule_stop_polling() -> None:
        asyncio.create_task(dp.stop_polling())

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _schedule_stop_polling)
        except NotImplementedError:
            pass

    poll_task = asyncio.create_task(poller(bot))

    log.info(
        "ready @%s db=%s poll=%ss vip_poll=%ss regular_poll=%ss sqlite_sync=%s",
        bot_ui.BOT_USERNAME or "?",
        SQLITE_PATH,
        CHECK_INTERVAL,
        VIP_CHECK_INTERVAL,
        REGULAR_CHECK_INTERVAL,
        SQLITE_SYNCHRONOUS,
    )
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        db_close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("shutdown")
