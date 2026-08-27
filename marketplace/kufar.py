"""Адаптер Kufar.by."""
from __future__ import annotations

import aiohttp

from kufar_fetch import fetch_ads_for_key, normalize_listing
from marketplace.keys import FetchKey
from marketplace.types import CURRENCY_BYN, NormalizedAd, SOURCE_KUFAR


class KufarAdapter:
    source = SOURCE_KUFAR

    def normalize(self, raw: dict) -> NormalizedAd | None:
        ad = normalize_listing(raw)
        if ad is None:
            return None
        ad["source"] = SOURCE_KUFAR
        ad["currency"] = CURRENCY_BYN
        return NormalizedAd(ad)

    async def fetch_for_key(
        self,
        key: FetchKey,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> list[NormalizedAd]:
        source, category, rgn, ar, models, memories = key
        if source != SOURCE_KUFAR:
            return []
        raw_ads = await fetch_ads_for_key(
            category,
            rgn,
            ar,
            models,
            memories,
            session=session,
        )
        out: list[NormalizedAd] = []
        for item in raw_ads:
            if not isinstance(item, dict):
                continue
            if item.get("source") == SOURCE_KUFAR and item.get("currency"):
                out.append(NormalizedAd(item))
            else:
                item = dict(item)
                item["source"] = SOURCE_KUFAR
                item["currency"] = CURRENCY_BYN
                out.append(NormalizedAd(item))
        return out


kufar_adapter = KufarAdapter()
