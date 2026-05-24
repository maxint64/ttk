import tempfile
import unittest
from pathlib import Path

from server import database


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.sqlite3"
        database.init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_activity_with_roles_and_members(self):
        """アクティビティに役割とメンバーを追加して一覧で確認できる"""
        activity = database.create_activity(self.db_path, "朝会")
        member = database.add_member(
            self.db_path, activity["id"], "田中", "tanaka@example.com"
        )
        role = database.add_role(self.db_path, activity["id"], "司会")

        activities = database.list_activities(self.db_path)

        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0]["name"], "朝会")
        self.assertEqual(activities[0]["roles"], [role])
        self.assertEqual(activities[0]["members"], [member])
        self.assertEqual(activities[0]["assignments"], [])

    def test_add_role_does_not_assign_member(self):
        """役割を追加しただけでは担当は自動作成されない"""
        activity = database.create_activity(self.db_path, "朝会")
        database.add_member(self.db_path, activity["id"], "田中", "tanaka@example.com")

        database.add_role(self.db_path, activity["id"], "司会")

        self.assertEqual(
            database.get_activity(self.db_path, activity["id"])["assignments"], []
        )

    def test_create_and_list_assignments(self):
        """担当を作成して一覧とアクティビティ詳細から取得できる"""
        activity = database.create_activity(self.db_path, "朝会")
        member = database.add_member(
            self.db_path, activity["id"], "田中", "tanaka@example.com"
        )
        role = database.add_role(self.db_path, activity["id"], "司会")

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
        self.assertRegex(
            assignment["created_at"],
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}$",
        )

    def test_list_assignments_on_returns_selected_day_or_not_found(self):
        """指定日の担当だけを取得し、存在しない日は未検出にする"""
        activity = database.create_activity(self.db_path, "朝会")
        member = database.add_member(
            self.db_path, activity["id"], "田中", "tanaka@example.com"
        )
        role = database.add_role(self.db_path, activity["id"], "司会")
        assignment = database.add_assignment(
            self.db_path, activity["id"], role["id"], member["id"], "2026-05-23"
        )

        self.assertEqual(
            database.list_assignments_on(self.db_path, activity["id"], "2026-05-23"),
            [assignment],
        )
        with self.assertRaises(database.NotFoundError):
            database.list_assignments_on(self.db_path, activity["id"], "2026-05-24")

    def test_assignment_replaces_role_member_for_same_day(self):
        """同じ日付と役割の担当は新しいメンバーで置き換える"""
        activity = database.create_activity(self.db_path, "朝会")
        first = database.add_member(
            self.db_path, activity["id"], "田中", "tanaka@example.com"
        )
        second = database.add_member(
            self.db_path, activity["id"], "佐藤", "sato@example.com"
        )
        role = database.add_role(self.db_path, activity["id"], "司会")

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
        """ローテーションで担当者が次のメンバーへ進む"""
        activity = database.create_activity(self.db_path, "朝会")
        first = database.add_member(
            self.db_path, activity["id"], "田中", "tanaka@example.com"
        )
        second = database.add_member(
            self.db_path, activity["id"], "佐藤", "sato@example.com"
        )
        database.add_member(self.db_path, activity["id"], "鈴木", "suzuki@example.com")
        role = database.add_role(self.db_path, activity["id"], "司会")
        database.add_assignment(
            self.db_path, activity["id"], role["id"], first["id"], "2026-05-23"
        )

        created = database.rotate_assignments(self.db_path, "2026-05-24")

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["member_id"], second["id"])
        self.assertEqual(created[0]["assigned_on"], "2026-05-24")

    def test_rotate_assignments_wraps_last_member_to_first(self):
        """最後のメンバーの次は最初のメンバーに戻る"""
        activity = database.create_activity(self.db_path, "朝会")
        first = database.add_member(
            self.db_path, activity["id"], "田中", "tanaka@example.com"
        )
        second = database.add_member(
            self.db_path, activity["id"], "佐藤", "sato@example.com"
        )
        role = database.add_role(self.db_path, activity["id"], "司会")
        database.add_assignment(
            self.db_path, activity["id"], role["id"], second["id"], "2026-05-23"
        )

        created = database.rotate_assignments(self.db_path, "2026-05-24")

        self.assertEqual(created[0]["member_id"], first["id"])

    def test_rotate_assignments_skips_roles_without_manual_assignment(self):
        """過去の担当がない役割はローテーション対象にしない"""
        activity = database.create_activity(self.db_path, "朝会")
        database.add_member(self.db_path, activity["id"], "田中", "tanaka@example.com")
        database.add_role(self.db_path, activity["id"], "司会")

        self.assertEqual(database.rotate_assignments(self.db_path, "2026-05-24"), [])
        self.assertEqual(database.list_assignments(self.db_path, activity["id"]), [])

    def test_rotate_assignments_keeps_existing_target_day_assignment(self):
        """対象日に既に担当がある場合は上書きしない"""
        activity = database.create_activity(self.db_path, "朝会")
        first = database.add_member(
            self.db_path, activity["id"], "田中", "tanaka@example.com"
        )
        second = database.add_member(
            self.db_path, activity["id"], "佐藤", "sato@example.com"
        )
        role = database.add_role(self.db_path, activity["id"], "司会")
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
        """担当には同じアクティビティの役割とメンバーが必要"""
        activity = database.create_activity(self.db_path, "朝会")
        other_activity = database.create_activity(self.db_path, "掃除当番")
        database.add_member(self.db_path, other_activity["id"], "佐藤", "sato@example.com")
        role = database.add_role(self.db_path, other_activity["id"], "床")
        member = database.add_member(
            self.db_path, activity["id"], "田中", "tanaka@example.com"
        )

        with self.assertRaises(database.NotFoundError):
            database.add_assignment(
                self.db_path, activity["id"], role["id"], member["id"], "2026-05-23"
            )

    def test_delete_activity_cascades_children(self):
        """アクティビティ削除で役割・メンバー・担当も削除される"""
        activity = database.create_activity(self.db_path, "掃除当番")
        member = database.add_member(
            self.db_path, activity["id"], "佐藤", "sato@example.com"
        )
        role = database.add_role(self.db_path, activity["id"], "床")
        database.add_assignment(
            self.db_path, activity["id"], role["id"], member["id"], "2026-05-23"
        )

        database.delete_activity(self.db_path, activity["id"])

        self.assertEqual(database.list_activities(self.db_path), [])

    def test_rejects_duplicate_role_in_activity(self):
        """同じアクティビティに同名の役割は追加できない"""
        activity = database.create_activity(self.db_path, "朝会")
        database.add_member(self.db_path, activity["id"], "田中", "tanaka@example.com")
        database.add_role(self.db_path, activity["id"], "司会")

        with self.assertRaises(database.ValidationError):
            database.add_role(self.db_path, activity["id"], "司会")

    def test_rejects_role_when_members_are_insufficient(self):
        """メンバー数を超える役割は追加できない"""
        activity = database.create_activity(self.db_path, "朝会")

        with self.assertRaisesRegex(
            database.ValidationError,
            "役割を追加するにはメンバーを追加してください。",
        ):
            database.add_role(self.db_path, activity["id"], "司会")

    def test_rejects_duplicate_member_email_in_activity(self):
        """同じアクティビティに同じメールアドレスは追加できない"""
        activity = database.create_activity(self.db_path, "朝会")
        database.add_member(self.db_path, activity["id"], "田中", "same@example.com")

        with self.assertRaises(database.ValidationError):
            database.add_member(self.db_path, activity["id"], "佐藤", "same@example.com")


if __name__ == "__main__":
    unittest.main()
