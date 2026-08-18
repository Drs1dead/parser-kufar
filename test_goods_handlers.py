"""Проверка, что ветка «Товары» не падает с NameError."""
import unittest

from handlers.goods_ui import (
    _goods_mobile_brands_keyboard,
    _goods_mobile_brands_text,
)


class GoodsUiImportTests(unittest.TestCase):
    def test_mobile_brands_screen_builds(self):
        text = _goods_mobile_brands_text()
        kb = _goods_mobile_brands_keyboard({"role": "regular", "keywords": []})
        self.assertIn("бренд", text.lower())
        self.assertNotIn("смартфоны", text.lower())
        self.assertTrue(kb.inline_keyboard)
        last_row = kb.inline_keyboard[-1]
        self.assertEqual(last_row[0].callback_data, "nav:home")


if __name__ == "__main__":
    unittest.main()
