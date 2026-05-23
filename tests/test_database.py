import tempfile
import unittest
from pathlib import Path

from ttk_backend import database


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.sqlite3"
        database.init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_activity_with_roles_and_members(self):
        activity = database.create_activity(self.db_path, " 朝会 ")
        role = database.add_role(self.db_path, activity["id"], "司会")
        member = database.add_member(self.db_path, activity["id"], "田中")

        activities = database.list_activities(self.db_path)

        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0]["name"], "朝会")
        self.assertEqual(activities[0]["roles"], [role])
        self.assertEqual(activities[0]["members"], [member])
        self.assertEqual(activities[0]["assignments"], [])

    def test_add_role_does_not_assign_member(self):
        activity = database.create_activity(self.db_path, "朝会")
        database.add_member(self.db_path, activity["id"], "田中")

        database.add_role(self.db_path, activity["id"], "司会")

        self.assertEqual(
            database.get_activity(self.db_path, activity["id"])["assignments"], []
        )

    def test_create_and_list_assignments(self):
        activity = database.create_activity(self.db_path, "朝会")
        role = database.add_role(self.db_path, activity["id"], "司会")
        member = database.add_member(self.db_path, activity["id"], "田中")

        assignment = database.add_assignment(
            self.db_path, activity["id"], role["id"], member["id"], "2026-05-23"
        )

        self.assertEqual(
            assignment,
            {
                "id": assignment["id"],
                "activity_id": activity["id"],
                "role_id": role["id"],
                "member_id": member["id"],
                "assigned_on": "2026-05-23",
                "created_at": assignment["created_at"],
            },
        )
        self.assertEqual(
            database.list_assignments(self.db_path, activity["id"]), [assignment]
        )
        self.assertEqual(
            database.get_activity(self.db_path, activity["id"])["assignments"],
            [assignment],
        )

    def test_assignment_replaces_role_member_for_same_day(self):
        activity = database.create_activity(self.db_path, "朝会")
        role = database.add_role(self.db_path, activity["id"], "司会")
        first = database.add_member(self.db_path, activity["id"], "田中")
        second = database.add_member(self.db_path, activity["id"], "佐藤")

        database.add_assignment(
            self.db_path, activity["id"], role["id"], first["id"], "2026-05-23"
        )
        assignment = database.add_assignment(
            self.db_path, activity["id"], role["id"], second["id"], "2026-05-23"
        )

        self.assertEqual(
            database.list_assignments(self.db_path, activity["id"]), [assignment]
        )

    def test_rotate_assignments_moves_to_next_member(self):
        activity = database.create_activity(self.db_path, "朝会")
        role = database.add_role(self.db_path, activity["id"], "司会")
        first = database.add_member(self.db_path, activity["id"], "田中")
        second = database.add_member(self.db_path, activity["id"], "佐藤")
        database.add_member(self.db_path, activity["id"], "鈴木")
        database.add_assignment(
            self.db_path, activity["id"], role["id"], first["id"], "2026-05-23"
        )

        created = database.rotate_assignments(self.db_path, "2026-05-24")

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["member_id"], second["id"])
        self.assertEqual(created[0]["assigned_on"], "2026-05-24")

    def test_rotate_assignments_wraps_last_member_to_first(self):
        activity = database.create_activity(self.db_path, "朝会")
        role = database.add_role(self.db_path, activity["id"], "司会")
        first = database.add_member(self.db_path, activity["id"], "田中")
        second = database.add_member(self.db_path, activity["id"], "佐藤")
        database.add_assignment(
            self.db_path, activity["id"], role["id"], second["id"], "2026-05-23"
        )

        created = database.rotate_assignments(self.db_path, "2026-05-24")

        self.assertEqual(created[0]["member_id"], first["id"])

    def test_rotate_assignments_skips_roles_without_manual_assignment(self):
        activity = database.create_activity(self.db_path, "朝会")
        database.add_role(self.db_path, activity["id"], "司会")
        database.add_member(self.db_path, activity["id"], "田中")

        self.assertEqual(database.rotate_assignments(self.db_path, "2026-05-24"), [])
        self.assertEqual(database.list_assignments(self.db_path, activity["id"]), [])

    def test_rotate_assignments_keeps_existing_target_day_assignment(self):
        activity = database.create_activity(self.db_path, "朝会")
        role = database.add_role(self.db_path, activity["id"], "司会")
        first = database.add_member(self.db_path, activity["id"], "田中")
        second = database.add_member(self.db_path, activity["id"], "佐藤")
        database.add_assignment(
            self.db_path, activity["id"], role["id"], first["id"], "2026-05-23"
        )
        manual = database.add_assignment(
            self.db_path, activity["id"], role["id"], second["id"], "2026-05-24"
        )

        self.assertEqual(database.rotate_assignments(self.db_path, "2026-05-24"), [])
        self.assertEqual(
            database.list_assignments(self.db_path, activity["id"])[0], manual
        )

    def test_assignment_requires_role_and_member_in_activity(self):
        activity = database.create_activity(self.db_path, "朝会")
        other_activity = database.create_activity(self.db_path, "掃除当番")
        role = database.add_role(self.db_path, other_activity["id"], "床")
        member = database.add_member(self.db_path, activity["id"], "田中")

        with self.assertRaises(database.NotFoundError):
            database.add_assignment(
                self.db_path, activity["id"], role["id"], member["id"], "2026-05-23"
            )

    def test_delete_activity_cascades_children(self):
        activity = database.create_activity(self.db_path, "掃除当番")
        role = database.add_role(self.db_path, activity["id"], "床")
        member = database.add_member(self.db_path, activity["id"], "佐藤")
        database.add_assignment(
            self.db_path, activity["id"], role["id"], member["id"], "2026-05-23"
        )

        database.delete_activity(self.db_path, activity["id"])

        self.assertEqual(database.list_activities(self.db_path), [])

    def test_rejects_blank_name(self):
        with self.assertRaises(database.ValidationError):
            database.create_activity(self.db_path, " ")


if __name__ == "__main__":
    unittest.main()
