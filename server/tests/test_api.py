import asyncio
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import httpx

from server import rotation
from server.server import create_app


class ApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 2
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.app = create_app(self.db_path, Path.cwd() / "app")
        transport = httpx.ASGITransport(app=self.app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.temp_dir.cleanup()

    async def test_activity_role_member_flow(self):
        """APIで活動・メンバー・役割・担当を作成して削除できる"""
        activity = await self.request_json("POST", "/api/activities", {"name": "勉強会"}, 201)
        member = await self.request_json(
            "POST",
            f"/api/activities/{activity['id']}/members",
            {"name": "山田", "email": "yamada@example.com"},
            201,
        )
        role = await self.request_json(
            "POST", f"/api/activities/{activity['id']}/roles", {"name": "発表"}, 201
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
        self.assertEqual(index["activities"][0]["role_member_skips"], [])

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

    async def test_role_member_skip_flow(self):
        """APIでスキップを設定・解除できる"""
        activity = await self.request_json("POST", "/api/activities", {"name": "勉強会"}, 201)
        member = await self.request_json(
            "POST",
            f"/api/activities/{activity['id']}/members",
            {"name": "山田", "email": "yamada@example.com"},
            201,
        )
        role = await self.request_json(
            "POST", f"/api/activities/{activity['id']}/roles", {"name": "発表"}, 201
        )

        skip = await self.request_json(
            "POST",
            f"/api/activities/{activity['id']}/roles/{role['id']}/skips",
            {"member_id": member["id"]},
            201,
        )

        index = await self.request_json("GET", "/api/activities")
        self.assertEqual(index["activities"][0]["role_member_skips"], [skip])

        await self.request_empty(
            "DELETE",
            f"/api/activities/{activity['id']}/roles/{role['id']}/skips/{member['id']}",
        )

        index = await self.request_json("GET", "/api/activities")
        self.assertEqual(index["activities"][0]["role_member_skips"], [])

    async def test_validation_errors_keep_existing_shape(self):
        """活動名の入力エラーは日本語のerrorレスポンスで返す"""
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

    async def test_openapi_uses_pydantic_response_models(self):
        """APIレスポンスのPydanticモデルをOpenAPIに反映する"""
        response = await self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        spec = response.json()
        schemas = spec["components"]["schemas"]
        activities_response = spec["paths"]["/api/activities"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        create_activity_response = spec["paths"]["/api/activities"]["post"]["responses"][
            "201"
        ]["content"]["application/json"]["schema"]

        self.assertEqual(
            activities_response, {"$ref": "#/components/schemas/ActivitiesResponse"}
        )
        self.assertEqual(
            create_activity_response, {"$ref": "#/components/schemas/ActivityResponse"}
        )
        self.assertIn("ActivityResponse", schemas)
        self.assertIn("AssignmentResponse", schemas)
        self.assertIn("ErrorResponse", schemas)

    async def test_role_and_member_text_validation_happens_in_api(self):
        """役割名とメンバー情報の文字種検証をAPI層で行う"""
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
        """重複役割・メンバー不足・重複メールをAPIエラーにする"""
        activity = await self.request_json("POST", "/api/activities", {"name": "勉強会"}, 201)
        await self.request_json(
            "POST",
            f"/api/activities/{activity['id']}/members",
            {"name": "田中", "email": "tanaka@example.com"},
            201,
        )
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

        insufficient_members = await self.client.post(
            f"/api/activities/{activity['id']}/roles", json={"name": "記録"}
        )
        self.assertEqual(insufficient_members.status_code, 400)
        self.assertEqual(
            insufficient_members.json(),
            {"error": "役割を追加するにはメンバーを追加してください。"},
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
        """不正なIDは400エラーとして返す"""
        response = await self.client.delete("/api/activities/not-a-number")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "IDが正しくありません。"})

    async def test_assignment_validation_errors(self):
        """担当作成と日付指定の入力エラーを日本語で返す"""
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

    async def test_event_stream_sends_assignment_change_events(self):
        """SSEで担当更新イベントをdata形式で配信する"""
        payload = '{"type":"assignments_changed","count":1}'
        subscribed = []

        def fake_subscribe(stop_requested):
            subscribed.append(callable(stop_requested))
            yield payload

        with mock.patch(
            "server.server.events.subscribe_events", side_effect=fake_subscribe
        ):
            response = await self.client.get("/api/events")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-cache")
        self.assertEqual(
            response.headers["content-type"].split(";")[0], "text/event-stream"
        )
        self.assertEqual(response.text, f"data: {payload}\n\n")
        self.assertEqual(subscribed, [True])

    async def test_large_rotation_scenario_through_api(self):
        """複数活動をAPIで作成し5日分のローテーション結果を確認する"""
        activities = []

        for activity_index in range(10):
            activity = await self.request_json(
                "POST", "/api/activities", {"name": f"活動{activity_index + 1}"}, 201
            )
            members = [
                await self.request_json(
                    "POST",
                    f"/api/activities/{activity['id']}/members",
                    {
                        "name": f"メンバー{member_index + 1}",
                        "email": (
                            f"activity{activity_index + 1}-"
                            f"member{member_index + 1}@example.com"
                        ),
                    },
                    201,
                )
                for member_index in range(5)
            ]
            roles = [
                await self.request_json(
                    "POST",
                    f"/api/activities/{activity['id']}/roles",
                    {"name": f"役割{role_index + 1}"},
                    201,
                )
                for role_index in range(5)
            ]

            for role_index, role in enumerate(roles):
                await self.request_json(
                    "POST",
                    f"/api/activities/{activity['id']}/assignments",
                    {
                        "role_id": role["id"],
                        "member_id": members[role_index]["id"],
                        "assigned_on": "2026-05-23",
                    },
                    201,
                )

            activities.append({"activity": activity, "roles": roles, "members": members})

        rotation_dates = [
            "2026-05-24",
            "2026-05-25",
            "2026-05-26",
            "2026-05-27",
            "2026-05-28",
        ]
        for target_on in rotation_dates:
            created = rotation.rotate_once(self.db_path, target_on)
            self.assertEqual(len(created), 50)

        index = await self.request_json("GET", "/api/activities")
        self.assertEqual(len(index["activities"]), 10)

        activities_by_id = {activity["id"]: activity for activity in index["activities"]}
        for scenario in activities:
            activity = activities_by_id[scenario["activity"]["id"]]
            self.assertEqual(len(activity["assignments"]), 30)

            for role_index, role in enumerate(scenario["roles"]):
                assignments = [
                    assignment
                    for assignment in activity["assignments"]
                    if assignment["role_id"] == role["id"]
                ]
                self.assertEqual(len(assignments), 6)
                assignments_by_date = {
                    assignment["assigned_on"]: assignment for assignment in assignments
                }

                all_dates = ["2026-05-23", *rotation_dates]
                self.assertEqual(set(assignments_by_date), set(all_dates))

                for day_offset, assigned_on in enumerate(all_dates):
                    expected_member = scenario["members"][
                        (role_index + day_offset) % len(scenario["members"])
                    ]
                    self.assertEqual(
                        assignments_by_date[assigned_on]["member_id"],
                        expected_member["id"],
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
