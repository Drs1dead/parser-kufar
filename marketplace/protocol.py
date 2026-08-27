"""Интерфейс адаптера маркетплейса."""
from __future__ import annotations

from typing import Protocol

import aiohttp

from marketplace.keys import FetchKey
from marketplace.types import NormalizedAd


class MarketplaceAdapter(Protocol):
    source: str

    def normalize(self, raw: dict) -> NormalizedAd | None: ...

    async def fetch_for_key(
        self,
        key: FetchKey,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> list[NormalizedAd]: ...
