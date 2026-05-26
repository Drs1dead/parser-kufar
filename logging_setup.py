"""Единая настройка логов для процесса бота."""
import logging
import sys

from config import LOG_LEVEL


def configure_logging() -> None:
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s %(name)s · %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    for name in ("aiogram", "aiohttp", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def log_exception(logger: logging.Logger, msg: str, *args) -> None:
    """Полный traceback только при LOG_LEVEL=DEBUG."""
    if logger.isEnabledFor(logging.DEBUG):
        logger.exception(msg, *args)
    else:
        logger.warning(msg, *args)
