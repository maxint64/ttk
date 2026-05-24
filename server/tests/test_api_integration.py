import asyncio
import tempfile
import unittest
from pathlib import Path

import httpx

from server import rotation
from server.server import create_app


class ApiIntegrationTest(unittest.IsolatedAsyncioTestCase):
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

    async def test_large_rotation_scenario_through_api(self):
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

        activities_by_id = {
            activity["id"]: activity for activity in index["activities"]
        }
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


if __name__ == "__main__":
    unittest.main()
