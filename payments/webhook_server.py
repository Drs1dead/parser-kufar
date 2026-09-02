"""HTTP webhook server for RollyPay (alongside Telegram polling)."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiohttp import web
from aiogram import Bot

from config import (
    ROLLYPAY_ENABLED,
    ROLLYPAY_SIGNING_SECRET,
    VIP_PAYMENT_POLL_SECONDS,
    WEBHOOK_HOST,
    WEBHOOK_PORT,
)
from payments.fulfillment import (
    fulfill_vip_payment,
    notify_vip_granted,
    poll_pending_vip_payments,
)
from payments.rollypay import verify_webhook_signature

log = logging.getLogger(__name__)


def _is_paid_event(payload: dict[str, Any]) -> bool:
    event = str(payload.get("event") or payload.get("type") or "").strip().lower()
    status = str(payload.get("status") or "").strip().lower()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if not status and isinstance(data, dict):
        status = str(data.get("status") or "").strip().lower()
    if event in ("payment.paid", "payment.succeeded"):
        return True
    return status in ("paid", "succeeded", "success")


def _extract_ids(payload: dict[str, Any]) -> tuple[str, str]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    order_id = str(
        payload.get("order_id")
        or data.get("order_id")
        or ""
    ).strip()
    payment_id = str(
        payload.get("payment_id")
        or payload.get("id")
        or data.get("payment_id")
        or data.get("id")
        or ""
    ).strip()
    return order_id, payment_id


async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "kufi-bot"})


async def handle_rollypay_webhook(request: web.Request) -> web.Response:
    bot: Bot | None = request.app.get("bot")
    raw = await request.read()
    ts = request.headers.get("X-Timestamp", "")
    sig = request.headers.get("X-Signature", "")
    if not verify_webhook_signature(raw, ts, sig):
        log.warning("rollypay webhook bad signature")
        return web.Response(status=401, text="invalid signature")
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return web.Response(status=400, text="bad json")
    if not isinstance(payload, dict):
        return web.Response(status=400, text="bad payload")

    if not _is_paid_event(payload):
        status = str(payload.get("status") or "").lower()
        if status in ("canceled", "cancelled", "expired", "chargeback"):
            from db import get_vip_payment_by_order, mark_vip_payment_status

            order_id, _ = _extract_ids(payload)
            if order_id and get_vip_payment_by_order(order_id):
                mark_vip_payment_status(
                    order_id, "canceled" if "cancel" in status else status
                )
        return web.Response(status=200, text="ok")

    order_id, payment_id = _extract_ids(payload)

    try:
        granted = await asyncio.to_thread(
            fulfill_vip_payment,
            order_id=order_id or None,
            payment_id=payment_id or None,
        )
    except Exception:
        log.exception("rollypay fulfill failed order=%s payment=%s", order_id, payment_id)
        return web.Response(status=500, text="fulfill error")
    if granted and bot is not None:
        asyncio.create_task(notify_vip_granted(bot, granted))
    return web.Response(status=200, text="ok")


def create_webhook_app(bot: Bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/health", handle_health)
    app.router.add_post("/webhooks/rollypay", handle_rollypay_webhook)
    return app


async def start_webhook_server(bot: Bot) -> web.AppRunner | None:
    if not ROLLYPAY_ENABLED:
        log.info("rollypay webhook server skipped (disabled)")
        return None
    if not ROLLYPAY_SIGNING_SECRET:
        log.warning("ROLLYPAY_SIGNING_SECRET missing — webhook verify will fail")
    app = create_webhook_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT)
    await site.start()
    log.info("webhook listening http://%s:%s", WEBHOOK_HOST, WEBHOOK_PORT)
    return runner


async def vip_payment_poll_loop(bot: Bot) -> None:
    if not ROLLYPAY_ENABLED:
        return
    while True:
        try:
            await asyncio.sleep(VIP_PAYMENT_POLL_SECONDS)
            n = await poll_pending_vip_payments(bot)
            if n:
                log.info("vip payment poll fulfilled=%s", n)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("vip payment poll loop error")
