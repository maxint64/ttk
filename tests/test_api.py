import tempfile
import unittest
from pathlib import Path

import httpx

from ttk_backend.server import create_app


class ApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.app = create_app(self.db_path, Path.cwd())
        transport = httpx.ASGITransport(app=self.app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.temp_dir.cleanup()

    async def test_activity_role_member_flow(self):
        activity = await self.request_json("POST", "/api/activities", {"name": "勉強会"}, 201)
        role = await self.request_json(
            "POST", f"/api/activities/{activity['id']}/roles", {"name": "発表"}, 201
        )
        member = await self.request_json(
            "POST", f"/api/activities/{activity['id']}/members", {"name": "山田"}, 201
        )

        index = await self.request_json("GET", "/api/activities")
        self.assertEqual(index["activities"][0]["roles"], [role])
        self.assertEqual(index["activities"][0]["members"], [member])

        await self.request_empty("DELETE", f"/api/activities/{activity['id']}/roles/{role['id']}")
        await self.request_empty(
            "DELETE", f"/api/activities/{activity['id']}/members/{member['id']}"
        )
        await self.request_empty("DELETE", f"/api/activities/{activity['id']}")

        index = await self.request_json("GET", "/api/activities")
        self.assertEqual(index["activities"], [])

    async def test_validation_errors_keep_existing_shape(self):
        response = await self.client.post("/api/activities", json={"name": " "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "name is required"})

    async def test_invalid_id_returns_bad_request(self):
        response = await self.client.delete("/api/activities/not-a-number")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "invalid id"})

    async def request_json(self, method, path, payload=None, expected_status=200):
        response = await self.client.request(method, path, json=payload)
        self.assertEqual(response.status_code, expected_status)
        return response.json()

    async def request_empty(self, method, path):
        response = await self.client.request(method, path)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")


if __name__ == "__main__":
    unittest.main()
