import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from ttk_backend.server import create_handler


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.sqlite3"
        handler = create_handler(self.db_path, Path.cwd())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def test_activity_role_member_flow(self):
        activity = self.request_json("POST", "/api/activities", {"name": "勉強会"})
        role = self.request_json(
            "POST", f"/api/activities/{activity['id']}/roles", {"name": "発表"}
        )
        member = self.request_json(
            "POST", f"/api/activities/{activity['id']}/members", {"name": "山田"}
        )

        index = self.request_json("GET", "/api/activities")
        self.assertEqual(index["activities"][0]["roles"], [role])
        self.assertEqual(index["activities"][0]["members"], [member])

        self.request_empty("DELETE", f"/api/activities/{activity['id']}/roles/{role['id']}")
        self.request_empty(
            "DELETE", f"/api/activities/{activity['id']}/members/{member['id']}"
        )
        self.request_empty("DELETE", f"/api/activities/{activity['id']}")

        index = self.request_json("GET", "/api/activities")
        self.assertEqual(index["activities"], [])

    def request_json(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))

    def request_empty(self, method, path):
        request = Request(self.base_url + path, method=method)
        with urlopen(request) as response:
            self.assertEqual(response.status, 204)


if __name__ == "__main__":
    unittest.main()

