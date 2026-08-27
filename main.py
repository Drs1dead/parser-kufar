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
    ADMIN_IDS,
    CHECK_INTERVAL,
    MARKET_DISCOUNT_THRESHOLD,
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
    if not ADMIN_IDS:
        log.warning("ADMIN_IDS empty — admin panel unavailable")
    if CHECK_INTERVAL < 1:
        log.error("CHECK_INTERVAL must be >= 1")
        sys.exit(1)
    if not 0 < MARKET_DISCOUNT_THRESHOLD < 1:
        log.error("MARKET_DISCOUNT_THRESHOLD must be between 0 and 1")
        sys.exit(1)

    init_db()

    from kufar_geo import geo_data_available, GEO_PATH

    if not geo_data_available():
        log.error("data/kufar_geo.json missing at %s — city text input disabled", GEO_PATH)
    else:
        log.info("geo map loaded path=%s", GEO_PATH)

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
