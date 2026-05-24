import tempfile
import unittest
from pathlib import Path
from unittest import mock

from server import stop


class StopTest(unittest.TestCase):
    def test_reads_live_server_pid_from_pid_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pid_path = Path(temp_dir) / "ttk.pid"
            pid_path.write_text("12345\n", encoding="utf-8")

            with (
                mock.patch.object(stop, "process_exists", return_value=True),
                mock.patch.object(stop, "looks_like_server_process", return_value=True),
            ):
                self.assertEqual(stop.read_pid_file_targets(pid_path), [12345])

            self.assertTrue(pid_path.exists())

    def test_removes_stale_pid_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pid_path = Path(temp_dir) / "ttk.pid"
            pid_path.write_text("12345\n", encoding="utf-8")

            with mock.patch.object(stop, "process_exists", return_value=False):
                self.assertEqual(stop.read_pid_file_targets(pid_path), [])

            self.assertFalse(pid_path.exists())


if __name__ == "__main__":
    unittest.main()
