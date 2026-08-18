"""Проверка, что ветка «Товары» не падает с NameError."""
import unittest

from handlers.goods_ui import (
    _goods_categories_keyboard,
    _goods_categories_text,
    _goods_mobile_brands_keyboard,
    _goods_mobile_brands_text,
)


class GoodsUiImportTests(unittest.TestCase):
    def test_category_root_builds(self):
        text = _goods_categories_text({"product_category": "phones"})
        kb = _goods_categories_keyboard({"role": "regular", "keywords": []})
        self.assertIn("категори", text.lower())
        self.assertTrue(kb.inline_keyboard)
        last_row = kb.inline_keyboard[-1]
        self.assertEqual(last_row[0].callback_data, "nav:home")

    def test_mobile_brands_screen_builds(self):
        text = _goods_mobile_brands_text()
        kb = _goods_mobile_brands_keyboard({"role": "regular", "keywords": []})
        self.assertIn("бренд", text.lower())
        self.assertTrue(kb.inline_keyboard)
        last_row = kb.inline_keyboard[-1]
        self.assertEqual(last_row[0].callback_data, "nav:goods")


if __name__ == "__main__":
    unittest.main()
