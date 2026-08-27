"""Реестр адаптеров маркетплейсов."""
from __future__ import annotations

from marketplace.kufar import kufar_adapter, KufarAdapter
from marketplace.protocol import MarketplaceAdapter
from marketplace.types import SOURCE_AVITO, SOURCE_KUFAR, normalize_primary_source

_ADAPTERS: dict[str, MarketplaceAdapter] = {
    SOURCE_KUFAR: kufar_adapter,
}


def get_adapter(source: str) -> MarketplaceAdapter:
    key = normalize_primary_source(source)
    adapter = _ADAPTERS.get(key)
    if adapter is None:
        if key == SOURCE_AVITO:
            raise NotImplementedError("Avito adapter is not implemented yet")
        raise ValueError(f"unknown marketplace source: {source!r}")
    return adapter


def adapter_for_user(user: dict | None) -> MarketplaceAdapter:
    return get_adapter(normalize_primary_source((user or {}).get("primary_source")))
