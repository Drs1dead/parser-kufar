"""Тесты правил отбора объявлений."""
import unittest

from filters import (
    REJECT_DEVICE_NOT_SELECTED,
    REJECT_EXCLUDE_PARTS,
    REJECT_EXCLUDE_TITLE,
    REJECT_NO_KEYWORDS,
    REJECT_NOT_SALE,
    ad_device_key,
    exchange_reject_reason,
    filter_reject_reason,
    is_exchange_ad,
    matches_filters,
)


def _ad(
    *,
    title: str = "",
    summary: str = "",
    description: str = "",
    price: int = 500,
) -> dict:
    return {
        "title": title,
        "summary": summary,
        "description": description,
        "price": price,
        "link": "https://example.com/ad/1",
    }


class ExchangeAdTests(unittest.TestCase):
    def test_screenshot_refusal_not_exchange(self) -> None:
        """Типичный шаблон продавца: ОБМЕН НЕ ИНТЕРЕСЕН (не «интересует»)."""
        ad = _ad(
            title="iphone 11",
            description=(
                "Ассортимент обновляется. ОБМЕН НЕ ИНТЕРЕСЕН. Краткое описание:"
            ),
        )
        self.assertFalse(is_exchange_ad(ad))
        self.assertEqual(exchange_reject_reason(ad), "exchange_refusal")

    def test_refusal_obmen_ne_with_punctuation(self) -> None:
        ad = _ad(description="обмен не интересен.")
        self.assertFalse(is_exchange_ad(ad))

    def test_refusal_regex_obmen_ne(self) -> None:
        ad = _ad(description="мы работаем без скидок. обмен не рассматривается")
        self.assertFalse(is_exchange_ad(ad))

    def test_refusal_all_caps_multiline(self) -> None:
        ad = _ad(
            description=(
                "Мы работаем БЕЗ СКИДОК И ТОРГА.\n"
                "ОБМЕН НЕ ИНТЕРЕСЕН.\n"
                "Состояние Приемлемое"
            ),
        )
        self.assertFalse(is_exchange_ad(ad))

    def test_bez_obmena(self) -> None:
        ad = _ad(description="торг без обмена")
        self.assertFalse(is_exchange_ad(ad))

    def test_positive_gotov_k_obmenu(self) -> None:
        ad = _ad(description="продам, готов к обмену на 13 pro")
        self.assertTrue(is_exchange_ad(ad))

    def test_positive_tolko_obmen(self) -> None:
        ad = _ad(title="iphone 12", description="только обмен")
        self.assertTrue(is_exchange_ad(ad))

    def test_bare_obmen_word_not_enough(self) -> None:
        ad = _ad(description="продам iphone, без дополнительных условий обмен")
        self.assertFalse(is_exchange_ad(ad))

    def test_positive_interesuet_obmen(self) -> None:
        ad = _ad(description="интересует обмен на более новую модель")
        self.assertTrue(is_exchange_ad(ad))


class SmartFilterTests(unittest.TestCase):
    def test_accessory_in_title_rejected(self) -> None:
        ad = _ad(title="чехол для iphone 11", summary="Смартфон")
        self.assertFalse(
            matches_filters(
                ad, 1000, ["iphone 11"], smart_filtering=True, device_filter=True
            )
        )
        self.assertEqual(
            filter_reject_reason(
                ad, 1000, ["iphone 11"], smart_filtering=True, device_filter=True
            ),
            REJECT_EXCLUDE_TITLE,
        )

    def test_not_sale_ne_kuplu_not_rejected(self) -> None:
        ad = _ad(title="iphone 11", summary="не куплю б/у, только продажа")
        self.assertTrue(
            matches_filters(
                ad, 1000, ["iphone 11"], smart_filtering=True, device_filter=True
            )
        )

    def test_not_sale_kuplu_rejected(self) -> None:
        ad = _ad(title="куплю iphone 11", summary="срочно")
        self.assertFalse(
            matches_filters(
                ad, 1000, ["iphone 11"], smart_filtering=True, device_filter=True
            )
        )
        self.assertEqual(
            filter_reject_reason(
                ad, 1000, ["iphone 11"], smart_filtering=True, device_filter=True
            ),
            REJECT_NOT_SALE,
        )

    def test_empty_keywords_rejected(self) -> None:
        ad = _ad(title="iphone 11", summary="Смартфон")
        self.assertFalse(
            matches_filters(ad, 1000, [], smart_filtering=True, device_filter=True)
        )
        self.assertEqual(
            filter_reject_reason(
                ad, 1000, [], smart_filtering=True, device_filter=True
            ),
            REJECT_NO_KEYWORDS,
        )

    def test_vip_all_devices_skips_keyword_filter(self) -> None:
        ad = _ad(title="Samsung Galaxy S25", summary="Смартфон")
        self.assertTrue(
            matches_filters(
                ad, 99_999_999, [], smart_filtering=True, device_filter=False
            )
        )

    def test_parent_keyword_matches_variant(self) -> None:
        """Выбран z flip — проходит объявление z flip 7."""
        ad = _ad(title="Samsung Galaxy Z Flip 7", summary="Смартфон")
        self.assertTrue(
            matches_filters(
                ad,
                2000,
                ["samsung galaxy z flip"],
                smart_filtering=True,
                device_filter=True,
            )
        )

    def test_screenshot_boards_below_market_rejected(self) -> None:
        """Платы iPhone — не целый телефон (VIP «ниже рынка»)."""
        ad = _ad(
            title="Платы iPhone 12 Pro / 12 Mini (Заблокированные)",
            summary="Смартфон",
            description="для swap, unlocking, donor parts",
        )
        self.assertFalse(
            matches_filters(
                ad, 99_999_999, [], smart_filtering=True, device_filter=False
            )
        )
        self.assertEqual(
            filter_reject_reason(
                ad, 99_999_999, [], smart_filtering=True, device_filter=False
            ),
            REJECT_EXCLUDE_PARTS,
        )

    def test_screenshot_parts_iphone11_rejected(self) -> None:
        ad = _ad(
            title="Запчасти для iPhone 11",
            summary="Смартфон",
            description="1 плата на icloud, 1акб, 2 корпуса, камеры",
        )
        self.assertFalse(
            matches_filters(
                ad, 99_999_999, [], smart_filtering=True, device_filter=False
            )
        )
        self.assertEqual(
            filter_reject_reason(
                ad, 99_999_999, [], smart_filtering=True, device_filter=False
            ),
            REJECT_EXCLUDE_PARTS,
        )


class SamsungFilterTests(unittest.TestCase):
    def test_samsung_ultra_short_title_matches_catalog_key(self) -> None:
        ad = _ad(title="Samsung S23 Ultra", summary="Смартфон")
        self.assertEqual(ad_device_key(ad), "samsung galaxy s23 ultra")

    def test_samsung_plus_symbol_matches_catalog_key(self) -> None:
        ad = _ad(title="Galaxy S24+", summary="Смартфон")
        self.assertEqual(ad_device_key(ad), "samsung galaxy s24 plus")

    def test_samsung_selected_keyword_passes_filters(self) -> None:
        ad = _ad(title="Samsung Galaxy S25", summary="Смартфон")
        self.assertTrue(
            matches_filters(
                ad,
                1000,
                ["samsung galaxy s25"],
                smart_filtering=True,
                device_filter=True,
            )
        )

    def test_wrong_model_rejected(self) -> None:
        ad = _ad(title="Samsung Galaxy S24", summary="Смартфон")
        self.assertEqual(
            filter_reject_reason(
                ad,
                1000,
                ["samsung galaxy s25"],
                smart_filtering=True,
                device_filter=True,
            ),
            REJECT_DEVICE_NOT_SELECTED,
        )

    def test_samsung_flip_short_title_matches_catalog_key(self) -> None:
        ad = _ad(title="Z Flip 7", summary="Смартфон")
        self.assertEqual(ad_device_key(ad), "samsung galaxy z flip 7")

    def test_samsung_fold_compact_title_matches_catalog_key(self) -> None:
        ad = _ad(title="Samsung zfold6", summary="Смартфон")
        self.assertEqual(ad_device_key(ad), "samsung galaxy z fold 6")


if __name__ == "__main__":
    unittest.main()
