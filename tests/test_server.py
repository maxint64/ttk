from datetime import datetime
import unittest

from ttk_backend.rotation import seconds_until_next_midnight


class ServerTest(unittest.TestCase):
    def test_seconds_until_next_midnight(self):
        now = datetime(2026, 5, 23, 23, 59, 30)

        self.assertEqual(seconds_until_next_midnight(now), 30)


if __name__ == "__main__":
    unittest.main()
