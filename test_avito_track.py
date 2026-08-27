"""Avito adapter stub and poll eligibility."""
import unittest
from unittest.mock import AsyncMock, patch

from marketplace.avito import AvitoAdapter
from marketplace.keys import user_is_avito_pollable, user_is_kufar_pollable
from marketplace.registry import get_adapter
from marketplace.types import COUNTRY_RU, SOURCE_AVITO, SOURCE_KUFAR


class AvitoAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_returns_empty_when_disabled(self) -> None:
        adapter = AvitoAdapter()
        key = (SOURCE_AVITO, "phones", "637640", "637640", ("iphone 15",), ("256",))
        with patch("marketplace.avito.AVITO_ENABLED", False):
            ads = await adapter.fetch_for_key(key)
        self.assertEqual(ads, [])

    async def test_fetch_raises_when_enabled_without_feed(self) -> None:
        adapter = AvitoAdapter()
        key = (SOURCE_AVITO, "phones", "637640", "637640", ("iphone 15",), ("256",))
        with patch("marketplace.avito.AVITO_ENABLED", True):
            with self.assertRaises(NotImplementedError):
                await adapter.fetch_for_key(key)


class AvitoRegistryTests(unittest.TestCase):
    def test_get_adapter_avito(self) -> None:
        adapter = get_adapter(SOURCE_AVITO)
        self.assertEqual(adapter.source, SOURCE_AVITO)

    def test_user_is_kufar_pollable(self) -> None:
        user = {"country": "by", "primary_source": "kufar"}
        self.assertTrue(user_is_kufar_pollable(user))
        self.assertFalse(user_is_avito_pollable(user))

    def test_user_is_avito_pollable_requires_enabled_and_city(self) -> None:
        user = {
            "country": COUNTRY_RU,
            "primary_source": SOURCE_AVITO,
            "avito_city_id": "637640",
        }
        with patch("marketplace.keys.AVITO_ENABLED", False):
            self.assertFalse(user_is_avito_pollable(user))
        with patch("marketplace.keys.AVITO_ENABLED", True):
            self.assertTrue(user_is_avito_pollable(user))


if __name__ == "__main__":
    unittest.main()
