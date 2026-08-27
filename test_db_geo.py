"""DB geo columns and update_geo."""
import os
import tempfile
import unittest

import db


class GeoDbTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_path = db.SQLITE_PATH
        path = os.path.join(self._tmp.name, "test.db")
        db.SQLITE_PATH = path
        db.conn = db._connect()
        db.init_db()

    def tearDown(self) -> None:
        db.conn.close()
        db.SQLITE_PATH = self._old_path
        db.conn = db._connect()
        self._tmp.cleanup()

    def test_update_geo_sets_fields(self) -> None:
        chat_id = 424242
        db.add_user(chat_id)
        geo = db.update_geo(chat_id, 1, 37, "Барановичи")
        self.assertEqual(geo["city_rgn"], 1)
        self.assertEqual(geo["city_ar"], 37)
        self.assertEqual(geo["city_label"], "Барановичи")
        user = db.get_user(chat_id)
        assert user is not None
        self.assertEqual(user["city_rgn"], 1)
        self.assertEqual(user["city_ar"], 37)
        self.assertEqual(user["city_label"], "Барановичи")


if __name__ == "__main__":
    unittest.main()
