"""Тройное отображение цен."""
import unittest

from currency_display import format_triple_price
from marketplace.types import COUNTRY_BY, COUNTRY_RU


class CurrencyDisplayTests(unittest.TestCase):
    def test_by_order_byn_usd_rub(self) -> None:
        text = format_triple_price(1000, country=COUNTRY_BY, price_usd_hint=320)
        self.assertTrue(text.startswith("1 000 Br"))
        self.assertIn("≈ 320$", text)
        self.assertIn("₽", text)

    def test_by_usd_fallback_without_hint(self) -> None:
        text = format_triple_price(1000, country=COUNTRY_BY)
        self.assertIn("Br", text)
        self.assertIn("$", text)
        self.assertIn("₽", text)

    def test_ru_order_rub_byn_usd(self) -> None:
        text = format_triple_price(100_000, country=COUNTRY_RU)
        self.assertTrue(text.endswith("$"))
        self.assertIn("₽", text.split("·")[0])
        self.assertIn("Br", text)

    def test_rounding(self) -> None:
        text = format_triple_price(5000, country=COUNTRY_BY, price_usd_hint=1600)
        self.assertIn("5 000 Br", text)
        self.assertIn("≈ 1600$", text)


if __name__ == "__main__":
    unittest.main()
