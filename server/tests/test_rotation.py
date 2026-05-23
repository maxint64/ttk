import argparse
import tempfile
import unittest
from pathlib import Path

from server import database, rotation
from server.run_rotation import valid_date


class RotationTest(unittest.TestCase):
    def test_rotate_once_initializes_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"

            self.assertEqual(rotation.rotate_once(db_path), [])
            self.assertTrue(db_path.exists())

    def test_rotate_once_can_target_date(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            database.init_db(db_path)
            activity = database.create_activity(db_path, "朝会")
            role = database.add_role(db_path, activity["id"], "司会")
            first = database.add_member(
                db_path, activity["id"], "田中", "tanaka@example.com"
            )
            second = database.add_member(
                db_path, activity["id"], "佐藤", "sato@example.com"
            )
            database.add_assignment(
                db_path, activity["id"], role["id"], first["id"], "2026-05-23"
            )

            created = rotation.rotate_once(db_path, "2026-05-24")

            self.assertEqual(len(created), 1)
            self.assertEqual(created[0]["assigned_on"], "2026-05-24")
            self.assertEqual(created[0]["member_id"], second["id"])

    def test_valid_date_rejects_invalid_date(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            valid_date("2026-13-99")


if __name__ == "__main__":
    unittest.main()
