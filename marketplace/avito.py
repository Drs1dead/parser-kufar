"""Адаптер Avito — mock или feed (Фаза 4)."""
from __future__ import annotations

import logging

import aiohttp

from avito_fetch import fetch_mock_ads_for_key
from config import AVITO_DEV_MOCK, AVITO_ENABLED
from marketplace.keys import FetchKey
from marketplace.types import CURRENCY_RUB, NormalizedAd, SOURCE_AVITO

log = logging.getLogger(__name__)


class AvitoAdapter:
    source = SOURCE_AVITO

    def normalize(self, raw: dict) -> NormalizedAd | None:
        if not isinstance(raw, dict):
            return None
        title = str(raw.get("title") or raw.get("subject") or "").strip()
        link = str(raw.get("link") or raw.get("url") or "").strip()
        if not title or not link:
            return None
        price = raw.get("price")
        if price is not None:
            try:
                price = int(price)
            except (TypeError, ValueError):
                price = None
        ad: dict = {
            "title": title,
            "link": link.split("?")[0],
            "price": price,
            "location": str(raw.get("location") or "").strip(),
            "summary": str(raw.get("summary") or "").strip(),
            "description": str(raw.get("description") or "").strip(),
            "photo_urls": list(raw.get("photo_urls") or raw.get("images") or []),
            "list_time": raw.get("list_time") or raw.get("published_at"),
            "source": SOURCE_AVITO,
            "currency": CURRENCY_RUB,
        }
        return NormalizedAd(ad)

    async def fetch_for_key(
        self,
        key: FetchKey,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> list[NormalizedAd]:
        del session
        if not AVITO_ENABLED:
            log.debug("avito fetch skipped — AVITO_ENABLED=false key=%s", key[:4])
            return []
        if AVITO_DEV_MOCK:
            return [NormalizedAd(ad) for ad in fetch_mock_ads_for_key(key)]
        raise NotImplementedError(
            "Avito feed adapter is not configured — set AVITO_FEED_URL when channel is ready"
        )


avito_adapter = AvitoAdapter()
