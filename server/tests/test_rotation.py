import argparse
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from server import database, rotation
from server.run_rotation import valid_date


class RotationTest(unittest.TestCase):
    def test_rotate_once_initializes_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"

            self.assertEqual(rotation.rotate_once(db_path), [])
            self.assertTrue(db_path.exists())

    def test_rotate_once_can_target_date(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            database.init_db(db_path)
            activity = database.create_activity(db_path, "朝会")
            first = database.add_member(
                db_path, activity["id"], "田中", "tanaka@example.com"
            )
            second = database.add_member(
                db_path, activity["id"], "佐藤", "sato@example.com"
            )
            role = database.add_role(db_path, activity["id"], "司会")
            database.add_assignment(
                db_path, activity["id"], role["id"], first["id"], "2026-05-23"
            )

            created = rotation.rotate_once(db_path, "2026-05-24")

            self.assertEqual(len(created), 1)
            self.assertEqual(created[0]["assigned_on"], "2026-05-24")
            self.assertEqual(created[0]["member_id"], second["id"])

    def test_run_logs_rotated_assignment_details(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            database.init_db(db_path)
            activity = database.create_activity(db_path, "朝会")
            first = database.add_member(
                db_path, activity["id"], "田中", "tanaka@example.com"
            )
            database.add_member(db_path, activity["id"], "佐藤", "sato@example.com")
            role = database.add_role(db_path, activity["id"], "司会")
            database.add_assignment(
                db_path, activity["id"], role["id"], first["id"], "2026-05-23"
            )

            output = io.StringIO()
            with redirect_stdout(output):
                rotation.run(db_path, "2026-05-24")

            self.assertEqual(
                output.getvalue().splitlines(),
                [
                    "rotated 1 assignments",
                    "2026-05-24 朝会 / 司会 -> 佐藤 <sato@example.com>",
                ],
            )

    def test_rotate_once_handles_role_member_count_combinations(self):
        counts = [1, 2, 3, 5]
        for role_count in counts:
            for member_count in counts:
                if member_count < role_count:
                    continue

                with self.subTest(role_count=role_count, member_count=member_count):
                    with tempfile.TemporaryDirectory() as temp_dir:
                        db_path = Path(temp_dir) / "test.sqlite3"
                        database.init_db(db_path)
                        activity = database.create_activity(
                            db_path, f"roles-{role_count}-members-{member_count}"
                        )
                        members = [
                            database.add_member(
                                db_path,
                                activity["id"],
                                f"メンバー{index + 1}",
                                f"member{index + 1}@example.com",
                            )
                            for index in range(member_count)
                        ]
                        roles = [
                            database.add_role(db_path, activity["id"], f"役割{index + 1}")
                            for index in range(role_count)
                        ]

                        for index, role in enumerate(roles):
                            database.add_assignment(
                                db_path,
                                activity["id"],
                                role["id"],
                                members[index % member_count]["id"],
                                "2026-05-23",
                            )

                        rotation_dates = [
                            "2026-05-24",
                            "2026-05-25",
                            "2026-05-26",
                            "2026-05-27",
                            "2026-05-28",
                        ]

                        for day_offset, target_on in enumerate(rotation_dates, start=1):
                            created = rotation.rotate_once(db_path, target_on)

                            self.assertEqual(len(created), role_count)
                            created_by_role = {
                                assignment["role_id"]: assignment for assignment in created
                            }
                            self.assertEqual(
                                set(created_by_role), {role["id"] for role in roles}
                            )
                            for role_index, role in enumerate(roles):
                                expected_member = members[
                                    (role_index + day_offset) % member_count
                                ]
                                self.assertEqual(
                                    created_by_role[role["id"]]["member_id"],
                                    expected_member["id"],
                                )
                                self.assertEqual(
                                    created_by_role[role["id"]]["assigned_on"],
                                    target_on,
                                )

    def test_valid_date_rejects_invalid_date(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            valid_date("2026-13-99")


if __name__ == "__main__":
    unittest.main()
