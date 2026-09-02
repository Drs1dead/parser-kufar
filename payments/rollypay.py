"""Async RollyPay API client + webhook HMAC verification."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import aiohttp

from config import (
    ROLLYPAY_API_KEY,
    ROLLYPAY_API_URL,
    ROLLYPAY_CALLBACK_URL,
    ROLLYPAY_SIGNING_SECRET,
    ROLLYPAY_TERMINAL_ID,
)

log = logging.getLogger(__name__)

WEBHOOK_MAX_AGE_SECONDS = 300


class RollyPayError(Exception):
    def __init__(self, message: str, *, status: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def format_amount_rub(amount: Decimal | str | float | int) -> str:
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value <= 0:
        raise ValueError("amount must be positive")
    return f"{value:.2f}"


def verify_webhook_signature(
    body: bytes,
    timestamp: str,
    signature: str,
    *,
    signing_secret: str | None = None,
    now: float | None = None,
    max_age_seconds: int = WEBHOOK_MAX_AGE_SECONDS,
) -> bool:
    secret = (signing_secret if signing_secret is not None else ROLLYPAY_SIGNING_SECRET).encode()
    if not secret or not signature or not timestamp:
        return False
    if not str(timestamp).isdigit():
        return False
    clock = time.time() if now is None else float(now)
    if abs(clock - int(timestamp)) > max_age_seconds:
        return False
    expected = hmac.new(
        secret,
        str(timestamp).encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    if not ROLLYPAY_API_KEY:
        raise RollyPayError("ROLLYPAY_API_KEY missing")
    url = f"{ROLLYPAY_API_URL}{path}"
    headers = {
        "X-API-Key": ROLLYPAY_API_KEY,
        "X-Nonce": str(uuid.uuid4()),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    owns = session is None
    sess = session or aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=25, connect=8)
    )
    try:
        async with sess.request(method, url, headers=headers, json=json_body) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RollyPayError(
                    f"RollyPay {method} {path} → {resp.status}",
                    status=resp.status,
                    body=text[:500],
                )
            if not text.strip():
                return {}
            data = json.loads(text)
            if not isinstance(data, dict):
                raise RollyPayError("RollyPay response is not an object")
            return data
    finally:
        if owns:
            await sess.close()


async def create_payment(
    *,
    amount_rub: Decimal | str,
    order_id: str,
    description: str,
    metadata: dict[str, Any] | None = None,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "terminal_id": ROLLYPAY_TERMINAL_ID,
        "amount": format_amount_rub(amount_rub),
        "payment_currency": "RUB",
        "order_id": order_id,
        "description": description[:200],
    }
    if ROLLYPAY_CALLBACK_URL:
        payload["callback_url"] = ROLLYPAY_CALLBACK_URL
    if metadata:
        payload["metadata"] = metadata
    log.info("rollypay create payment order_id=%s amount=%s", order_id, payload["amount"])
    return await _request("POST", "/api/v1/payments", json_body=payload, session=session)


async def get_payment(
    payment_id: str,
    *,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    pid = (payment_id or "").strip()
    if not pid:
        raise RollyPayError("payment_id empty")
    return await _request("GET", f"/api/v1/payments/{pid}", session=session)


async def get_rub_usdt_rate(
    *,
    session: aiohttp.ClientSession | None = None,
) -> Decimal:
    data = await _request(
        "GET",
        f"/api/v1/rate?terminal_id={ROLLYPAY_TERMINAL_ID}",
        session=session,
    )
    raw = data.get("rate") or data.get("rub_usdt") or data.get("value")
    if raw is None and isinstance(data.get("data"), dict):
        inner = data["data"]
        raw = inner.get("rate") or inner.get("rub_usdt") or inner.get("value")
    if raw is None:
        raise RollyPayError("rate missing in response", body=str(data)[:300])
    rate = Decimal(str(raw))
    if rate <= 0:
        raise RollyPayError(f"invalid rate: {rate}")
    return rate
