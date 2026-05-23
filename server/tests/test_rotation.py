import tempfile
import unittest
from pathlib import Path

from server import rotation


class RotationTest(unittest.TestCase):
    def test_rotate_once_initializes_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"

            self.assertEqual(rotation.rotate_once(db_path), [])
            self.assertTrue(db_path.exists())


if __name__ == "__main__":
    unittest.main()
