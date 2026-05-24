import tempfile
import unittest
from pathlib import Path

import httpx

from server.server import create_app


class ApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.app = create_app(self.db_path, Path.cwd() / "app")
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
            "POST",
            f"/api/activities/{activity['id']}/members",
            {"name": "山田", "email": "yamada@example.com"},
            201,
        )
        assignment = await self.request_json(
            "POST",
            f"/api/activities/{activity['id']}/assignments",
            {
                "role_id": role["id"],
                "member_id": member["id"],
                "assigned_on": "2026-05-23",
            },
            201,
        )

        index = await self.request_json("GET", "/api/activities")
        self.assertEqual(index["activities"][0]["roles"], [role])
        self.assertEqual(index["activities"][0]["members"], [member])
        self.assertEqual(index["activities"][0]["assignments"], [assignment])

        assignments = await self.request_json(
            "GET", f"/api/activities/{activity['id']}/assignments"
        )
        self.assertEqual(assignments["assignments"], [assignment])

        assignments_on = await self.request_json(
            "GET",
            f"/api/activities/{activity['id']}/assignments/dates/2026-05-23",
        )
        self.assertEqual(assignments_on["assignments"], [assignment])

        missing_assignments = await self.client.get(
            f"/api/activities/{activity['id']}/assignments/dates/2026-05-24"
        )
        self.assertEqual(missing_assignments.status_code, 404)
        self.assertEqual(missing_assignments.json(), {"error": "この日の担当データはありません。"})

        await self.request_empty(
            "DELETE", f"/api/activities/{activity['id']}/assignments/{assignment['id']}"
        )
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
        self.assertEqual(response.json(), {"error": "名前は必須です。"})

        too_long = await self.client.post("/api/activities", json={"name": "あ" * 145})
        self.assertEqual(too_long.status_code, 400)
        self.assertEqual(
            too_long.json(), {"error": "名前は144文字以内で入力してください。"}
        )

        invisible = await self.client.post(
            "/api/activities", json={"name": "\u200b勉強会"}
        )
        self.assertEqual(invisible.status_code, 400)
        self.assertEqual(
            invisible.json(), {"error": "名前に使用できない文字が含まれています。"}
        )

    async def test_role_and_member_text_validation_happens_in_api(self):
        activity = await self.request_json("POST", "/api/activities", {"name": "勉強会"}, 201)

        bad_role = await self.client.post(
            f"/api/activities/{activity['id']}/roles", json={"name": "発\u0007表"}
        )
        self.assertEqual(bad_role.status_code, 400)
        self.assertEqual(bad_role.json(), {"error": "名前に使用できない文字が含まれています。"})

        bad_member_name = await self.client.post(
            f"/api/activities/{activity['id']}/members",
            json={"name": "\u200b山田", "email": "yamada@example.com"},
        )
        self.assertEqual(bad_member_name.status_code, 400)
        self.assertEqual(
            bad_member_name.json(), {"error": "名前に使用できない文字が含まれています。"}
        )

        bad_member_email = await self.client.post(
            f"/api/activities/{activity['id']}/members",
            json={"name": "山田", "email": "yamada\u200c@example.com"},
        )
        self.assertEqual(bad_member_email.status_code, 400)
        self.assertEqual(
            bad_member_email.json(), {"error": "メールアドレスに使用できない文字が含まれています。"}
        )

    async def test_duplicate_role_and_member_email_errors(self):
        activity = await self.request_json("POST", "/api/activities", {"name": "勉強会"}, 201)
        await self.request_json(
            "POST", f"/api/activities/{activity['id']}/roles", {"name": "発表"}, 201
        )
        duplicate_role = await self.client.post(
            f"/api/activities/{activity['id']}/roles", json={"name": "発表"}
        )
        self.assertEqual(duplicate_role.status_code, 400)
        self.assertEqual(
            duplicate_role.json(), {"error": "このアクティビティには同じ役割が既にあります。"}
        )

        await self.request_json(
            "POST",
            f"/api/activities/{activity['id']}/members",
            {"name": "山田", "email": "same@example.com"},
            201,
        )
        duplicate_email = await self.client.post(
            f"/api/activities/{activity['id']}/members",
            json={"name": "佐藤", "email": "SAME@example.com"},
        )
        self.assertEqual(duplicate_email.status_code, 400)
        self.assertEqual(
            duplicate_email.json(),
            {"error": "このアクティビティには同じメールアドレスのメンバーが既にいます。"},
        )

    async def test_invalid_id_returns_bad_request(self):
        response = await self.client.delete("/api/activities/not-a-number")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "IDが正しくありません。"})

    async def test_assignment_validation_errors(self):
        activity = await self.request_json("POST", "/api/activities", {"name": "勉強会"}, 201)

        missing_role = await self.client.post(
            f"/api/activities/{activity['id']}/assignments",
            json={"member_id": 1, "assigned_on": "2026-05-23"},
        )
        self.assertEqual(missing_role.status_code, 400)
        self.assertEqual(missing_role.json(), {"error": "役割IDは必須です。"})

        bad_date = await self.client.post(
            f"/api/activities/{activity['id']}/assignments",
            json={"role_id": 1, "member_id": 1, "assigned_on": "2026-13-99"},
        )
        self.assertEqual(bad_date.status_code, 400)
        self.assertEqual(
            bad_date.json(), {"error": "担当日はYYYY-MM-DD形式の正しい日付を入力してください。"}
        )

        bad_path_date = await self.client.get(
            f"/api/activities/{activity['id']}/assignments/dates/2026-13-99"
        )
        self.assertEqual(bad_path_date.status_code, 400)
        self.assertEqual(
            bad_path_date.json(),
            {"error": "担当日はYYYY-MM-DD形式の正しい日付を入力してください。"},
        )

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
