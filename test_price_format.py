"""UI price formatting by country."""
import unittest

from config import format_price_for_country, format_price_for_user
from marketplace.types import COUNTRY_RU, SOURCE_AVITO, SOURCE_KUFAR


class PriceFormatTests(unittest.TestCase):
    def test_ru_country_shows_rub(self) -> None:
        self.assertIn("₽", format_price_for_country(50000, COUNTRY_RU))

    def test_avito_source_shows_rub(self) -> None:
        self.assertIn("₽", format_price_for_country(5000, "by", primary_source=SOURCE_AVITO))

    def test_by_kufar_shows_br(self) -> None:
        self.assertIn("Br", format_price_for_country(500, "by", primary_source=SOURCE_KUFAR))

    def test_format_price_for_user_ru(self) -> None:
        user = {"country": COUNTRY_RU, "primary_source": SOURCE_AVITO}
        self.assertIn("₽", format_price_for_user(142500, user))


if __name__ == "__main__":
    unittest.main()
