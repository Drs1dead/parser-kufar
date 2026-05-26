"""Сборка всех Telegram-роутеров."""
from aiogram import Router

from .admin import admin_router
from .goods import router as goods_router
from .nav import router as nav_router
from .start import router as start_router

router = Router()
# Сначала узкие хендлеры (FSM, callback), в конце — /start и «любой текст»
router.include_router(nav_router)
router.include_router(goods_router)
router.include_router(admin_router)
router.include_router(start_router)

__all__ = ["router"]
