"""VIP payment fulfillment: create invoice + grant after paid."""
from __future__ import annotations

import logging
import time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import aiohttp
from aiogram import Bot
from aiogram.enums import ParseMode

from config import (
    ROLLYPAY_ENABLED,
    VIP_PLAN_RUB_OVERRIDE,
    get_vip_plan,
)
from db import (
    create_vip_payment_row,
    get_vip_payment_by_order,
    get_vip_payment_by_payment_id,
    list_pending_vip_payments,
    mark_vip_payment_paid,
    mark_vip_payment_status,
    set_vip,
    update_vip_payment_provider,
)
from payments.rollypay import (
    RollyPayError,
    create_payment,
    get_payment,
    get_rub_usdt_rate,
)

log = logging.getLogger(__name__)


def usd_to_rub_amount(usd: Decimal | float | int, rate: Decimal) -> Decimal:
    amount = (Decimal(str(usd)) * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount < Decimal("1.00"):
        amount = Decimal("1.00")
    return amount


async def resolve_plan_amount_rub(
    plan_id: str,
    *,
    session: aiohttp.ClientSession | None = None,
) -> tuple[dict[str, int | float], Decimal]:
    plan = get_vip_plan(plan_id)
    if plan is None:
        raise ValueError(f"unknown plan: {plan_id}")
    override = VIP_PLAN_RUB_OVERRIDE.get(plan_id)
    if override:
        return plan, Decimal(override).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rate = await get_rub_usdt_rate(session=session)
    return plan, usd_to_rub_amount(plan["usd"], rate)


def make_order_id(chat_id: int, plan_id: str) -> str:
    return f"vip_{chat_id}_{plan_id}_{int(time.time())}"


async def start_vip_checkout(
    chat_id: int,
    plan_id: str,
    *,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    if not ROLLYPAY_ENABLED:
        raise RollyPayError("RollyPay disabled")
    plan, amount_rub = await resolve_plan_amount_rub(plan_id, session=session)
    days = int(plan["days"])
    usd = float(plan["usd"])
    order_id = make_order_id(chat_id, plan_id)
    create_vip_payment_row(
        order_id=order_id,
        chat_id=chat_id,
        plan=plan_id,
        days=days,
        amount_usd=usd,
        amount_rub=str(amount_rub),
    )
    description = f"Kufi VIP {days} days"
    try:
        resp = await create_payment(
            amount_rub=amount_rub,
            order_id=order_id,
            description=description,
            metadata={"chat_id": str(chat_id), "plan": plan_id, "days": str(days)},
            session=session,
        )
    except Exception:
        mark_vip_payment_status(order_id, "canceled")
        raise
    payment_id = str(resp.get("payment_id") or resp.get("id") or "").strip()
    pay_url = str(resp.get("pay_url") or resp.get("payment_url") or "").strip()
    if not payment_id or not pay_url:
        mark_vip_payment_status(order_id, "canceled")
        raise RollyPayError("payment_id/pay_url missing", body=str(resp)[:300])
    update_vip_payment_provider(order_id, payment_id=payment_id, pay_url=pay_url)
    row = get_vip_payment_by_order(order_id)
    assert row is not None
    return row


def fulfill_vip_payment(
    *,
    order_id: str | None = None,
    payment_id: str | None = None,
) -> dict[str, Any] | None:
    """Idempotent: mark paid + set_vip. Returns payment row if newly granted."""
    row = None
    if order_id:
        row = get_vip_payment_by_order(order_id)
    if row is None and payment_id:
        row = get_vip_payment_by_payment_id(payment_id)
    if row is None:
        return None
    if row.get("status") == "paid":
        return None
    oid = str(row["order_id"])
    pid = payment_id or row.get("payment_id")
    granted = mark_vip_payment_paid(oid, payment_id=str(pid) if pid else None)
    if not granted:
        return None
    chat_id = int(row["chat_id"])
    days = int(row["days"])
    set_vip(chat_id, days=days)
    log.info("vip granted chat_id=%s days=%s order_id=%s", chat_id, days, oid)
    updated = get_vip_payment_by_order(oid)
    return updated


async def notify_vip_granted(bot: Bot, row: dict[str, Any]) -> None:
    chat_id = int(row["chat_id"])
    days = int(row["days"])
    try:
        await bot.send_message(
            chat_id,
            f"✅ <b>VIP активирован</b> на <b>{days}</b> дн.\n"
            "Оплата получена — уведомления VIP уже доступны.",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        log.exception("notify vip failed chat_id=%s", chat_id)


async def check_and_fulfill_payment(
    order_id: str,
    *,
    bot: Bot | None = None,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any] | None:
    row = get_vip_payment_by_order(order_id)
    if row is None:
        return None
    if row.get("status") == "paid":
        return None
    payment_id = str(row.get("payment_id") or "").strip()
    if not payment_id:
        return None
    data = await get_payment(payment_id, session=session)
    status = str(data.get("status") or "").strip().lower()
    event = str(data.get("event") or "").strip().lower()
    paid = status in ("paid", "succeeded", "success") or event == "payment.paid"
    if status in ("canceled", "cancelled", "expired", "chargeback"):
        mark_vip_payment_status(order_id, "canceled" if "cancel" in status else status)
        return None
    if not paid:
        return None
    granted = fulfill_vip_payment(order_id=order_id, payment_id=payment_id)
    if granted and bot is not None:
        await notify_vip_granted(bot, granted)
    return granted


async def poll_pending_vip_payments(bot: Bot) -> int:
    """Backup path when webhook is delayed. Returns number newly fulfilled."""
    if not ROLLYPAY_ENABLED:
        return 0
    pending = list_pending_vip_payments(limit=40)
    if not pending:
        return 0
    done = 0
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=20, connect=6)
    ) as session:
        for row in pending:
            try:
                granted = await check_and_fulfill_payment(
                    str(row["order_id"]),
                    bot=bot,
                    session=session,
                )
                if granted:
                    done += 1
            except RollyPayError as exc:
                log.warning(
                    "vip poll failed order=%s: %s",
                    row.get("order_id"),
                    exc,
                )
            except Exception:
                log.exception("vip poll error order=%s", row.get("order_id"))
    return done
