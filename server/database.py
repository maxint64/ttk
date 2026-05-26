from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config

from .config import PROJECT_ROOT

SKIP_TYPE_ONCE = "once"
SKIP_TYPE_UNTIL_DELETED = "until_deleted"
VALID_SKIP_TYPES = {SKIP_TYPE_ONCE, SKIP_TYPE_UNTIL_DELETED}


def connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: str | Path) -> None:
    command.upgrade(migration_config(db_path), "head")


def migration_config(db_path: str | Path) -> Config:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["db_path"] = db_path
    return config


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass


def list_activities(db_path: str | Path) -> list[dict[str, Any]]:
    with connect(db_path) as connection:
        activities = [
            dict(row)
            for row in connection.execute(
                "SELECT id, name, created_at FROM activities ORDER BY id DESC"
            ).fetchall()
        ]
        roles = _group_items(connection, "roles")
        members = _group_items(connection, "members")
        assignments = _group_assignments(connection)
        role_member_skips = _group_role_member_skips(connection)

    for activity in activities:
        activity["roles"] = roles.get(activity["id"], [])
        activity["members"] = members.get(activity["id"], [])
        activity["assignments"] = assignments.get(activity["id"], [])
        activity["role_member_skips"] = role_member_skips.get(activity["id"], [])

    return activities


def create_activity(db_path: str | Path, name: str) -> dict[str, Any]:
    with connect(db_path) as connection:
        cursor = connection.execute("INSERT INTO activities (name) VALUES (?)", (name,))
        activity_id = cursor.lastrowid

    return get_activity(db_path, activity_id)


def delete_activity(db_path: str | Path, activity_id: int) -> None:
    with connect(db_path) as connection:
        cursor = connection.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
        if cursor.rowcount == 0:
            raise NotFoundError("アクティビティが見つかりませんでした。")


def add_role(db_path: str | Path, activity_id: int, name: str) -> dict[str, Any]:
    with connect(db_path) as connection:
        _require_activity(connection, activity_id)
        if _item_exists(connection, "roles", activity_id, "name", name):
            raise ValidationError("このアクティビティには同じ役割が既にあります。")
        if _item_count(connection, "roles", activity_id) + 1 > _item_count(
            connection, "members", activity_id
        ):
            raise ValidationError("役割を追加するにはメンバーを追加してください。")

        try:
            cursor = connection.execute(
                "INSERT INTO roles (activity_id, name) VALUES (?, ?)",
                (activity_id, name),
            )
        except sqlite3.IntegrityError as error:
            raise ValidationError("このアクティビティには同じ役割が既にあります。") from error

        role_id = cursor.lastrowid
        row = connection.execute(
            "SELECT id, name, created_at FROM roles WHERE id = ?", (role_id,)
        ).fetchone()

    return dict(row)


def add_member(
    db_path: str | Path, activity_id: int, name: str, email: str
) -> dict[str, Any]:
    with connect(db_path) as connection:
        _require_activity(connection, activity_id)
        if _item_exists(connection, "members", activity_id, "email", email):
            raise ValidationError("このアクティビティには同じメールアドレスのメンバーが既にいます。")

        try:
            cursor = connection.execute(
                "INSERT INTO members (activity_id, name, email) VALUES (?, ?, ?)",
                (activity_id, name, email),
            )
        except sqlite3.IntegrityError as error:
            raise ValidationError(
                "このアクティビティには同じメールアドレスのメンバーが既にいます。"
            ) from error

        member_id = cursor.lastrowid
        row = connection.execute(
            "SELECT id, name, email, created_at FROM members WHERE id = ?",
            (member_id,),
        ).fetchone()

    return dict(row)


def delete_role(db_path: str | Path, activity_id: int, role_id: int) -> None:
    _delete_activity_item(db_path, "roles", activity_id, role_id)


def delete_member(db_path: str | Path, activity_id: int, member_id: int) -> None:
    _delete_activity_item(db_path, "members", activity_id, member_id)


def add_role_member_skip(
    db_path: str | Path,
    activity_id: int,
    role_id: int,
    member_id: int,
    skip_type: str = SKIP_TYPE_ONCE,
) -> dict[str, Any]:
    skip_type = _clean_skip_type(skip_type)
    with connect(db_path) as connection:
        _require_activity(connection, activity_id)
        _require_activity_item(
            connection, "roles", activity_id, role_id, "役割が見つかりませんでした。"
        )
        _require_activity_item(
            connection, "members", activity_id, member_id, "メンバーが見つかりませんでした。"
        )
        connection.execute(
            """
            INSERT INTO role_member_skips
                (activity_id, role_id, member_id, skip_type, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(activity_id, role_id, member_id) DO UPDATE SET
                skip_type = excluded.skip_type,
                created_at = excluded.created_at
            """,
            (activity_id, role_id, member_id, skip_type, current_timestamp_ms()),
        )
        skip_id = connection.execute(
            """
            SELECT id
            FROM role_member_skips
            WHERE activity_id = ? AND role_id = ? AND member_id = ?
            """,
            (activity_id, role_id, member_id),
        ).fetchone()["id"]
        row = connection.execute(
            """
            SELECT id, activity_id, role_id, member_id, skip_type, created_at
            FROM role_member_skips
            WHERE id = ?
            """,
            (skip_id,),
        ).fetchone()

    return dict(row)


def delete_role_member_skip(
    db_path: str | Path, activity_id: int, role_id: int, member_id: int
) -> None:
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            DELETE FROM role_member_skips
            WHERE activity_id = ? AND role_id = ? AND member_id = ?
            """,
            (activity_id, role_id, member_id),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("スキップ設定が見つかりませんでした。")


def list_assignments(db_path: str | Path, activity_id: int) -> list[dict[str, Any]]:
    with connect(db_path) as connection:
        _require_activity(connection, activity_id)
        return _group_assignments(connection).get(activity_id, [])


def list_assignments_on(
    db_path: str | Path, activity_id: int, assigned_on: str
) -> list[dict[str, Any]]:
    with connect(db_path) as connection:
        _require_activity(connection, activity_id)
        rows = connection.execute(
            """
            SELECT id, activity_id, role_id, member_id, assigned_on, created_at
            FROM role_assignments
            WHERE activity_id = ? AND assigned_on = ?
            ORDER BY id ASC
            """,
            (activity_id, assigned_on),
        ).fetchall()

    if not rows:
        raise NotFoundError("この日の担当データはありません。")
    return [dict(row) for row in rows]


def add_assignment(
    db_path: str | Path,
    activity_id: int,
    role_id: int,
    member_id: int,
    assigned_on: str | None = None,
) -> dict[str, Any]:
    assigned_on = _clean_assigned_on(assigned_on)
    with connect(db_path) as connection:
        _require_activity(connection, activity_id)
        _require_activity_item(
            connection, "roles", activity_id, role_id, "役割が見つかりませんでした。"
        )
        _require_activity_item(
            connection, "members", activity_id, member_id, "メンバーが見つかりませんでした。"
        )
        if _is_role_member_skipped(connection, activity_id, role_id, member_id):
            raise ValidationError("このメンバーは指定した役割をスキップ中です。")

        connection.execute(
            """
            DELETE FROM role_assignments
            WHERE activity_id = ? AND role_id = ? AND assigned_on = ?
            """,
            (activity_id, role_id, assigned_on),
        )
        cursor = connection.execute(
            """
            INSERT INTO role_assignments
                (activity_id, role_id, member_id, assigned_on, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (activity_id, role_id, member_id, assigned_on, current_timestamp_ms()),
        )
        assignment_id = cursor.lastrowid

        row = connection.execute(
            """
            SELECT id, activity_id, role_id, member_id, assigned_on, created_at
            FROM role_assignments
            WHERE id = ?
            """,
            (assignment_id,),
        ).fetchone()

    return dict(row)


def rotate_assignments(db_path: str | Path, target_on: str | None = None) -> list[dict[str, Any]]:
    target_on = _clean_assigned_on(target_on)
    with connect(db_path) as connection:
        roles = connection.execute(
            "SELECT id, activity_id FROM roles ORDER BY activity_id ASC, id ASC"
        ).fetchall()
        created: list[dict[str, Any]] = []

        for role in roles:
            activity_id = role["activity_id"]
            role_id = role["id"]
            if _assignment_exists(connection, activity_id, role_id, target_on):
                continue

            latest = connection.execute(
                """
                SELECT member_id
                FROM role_assignments
                WHERE activity_id = ? AND role_id = ? AND assigned_on < ?
                ORDER BY assigned_on DESC, id DESC
                LIMIT 1
                """,
                (activity_id, role_id, target_on),
            ).fetchone()
            if latest is None:
                continue

            members = connection.execute(
                """
                SELECT id
                FROM members
                WHERE activity_id = ?
                ORDER BY id ASC
                """,
                (activity_id,),
            ).fetchall()
            member_ids = [member["id"] for member in members]
            if not member_ids:
                continue

            next_member_id = _next_member_id_for_rotation(
                connection, activity_id, role_id, member_ids, latest["member_id"]
            )
            if next_member_id is None:
                continue
            cursor = connection.execute(
                """
                INSERT INTO role_assignments
                    (activity_id, role_id, member_id, assigned_on, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (activity_id, role_id, next_member_id, target_on, current_timestamp_ms()),
            )
            row = connection.execute(
                """
                SELECT id, activity_id, role_id, member_id, assigned_on, created_at
                FROM role_assignments
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            created.append(dict(row))

    return created


def describe_assignments(
    db_path: str | Path, assignment_ids: list[int]
) -> list[dict[str, Any]]:
    if not assignment_ids:
        return []

    placeholders = ", ".join("?" for _ in assignment_ids)
    with connect(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                role_assignments.id,
                role_assignments.assigned_on,
                activities.name AS activity_name,
                roles.name AS role_name,
                members.name AS member_name,
                members.email AS member_email
            FROM role_assignments
            JOIN activities ON activities.id = role_assignments.activity_id
            JOIN roles ON roles.id = role_assignments.role_id
            JOIN members ON members.id = role_assignments.member_id
            WHERE role_assignments.id IN ({placeholders})
            """,
            assignment_ids,
        ).fetchall()

    by_id = {row["id"]: dict(row) for row in rows}
    return [by_id[assignment_id] for assignment_id in assignment_ids if assignment_id in by_id]


def delete_assignment(db_path: str | Path, activity_id: int, assignment_id: int) -> dict[str, Any]:
    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, activity_id, role_id, member_id, assigned_on, created_at
            FROM role_assignments
            WHERE id = ? AND activity_id = ?
            """,
            (assignment_id, activity_id),
        ).fetchone()
        if row is None:
            raise NotFoundError("担当が見つかりませんでした。")
        cursor = connection.execute(
            "DELETE FROM role_assignments WHERE id = ? AND activity_id = ?",
            (assignment_id, activity_id),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("担当が見つかりませんでした。")
    return dict(row)


def get_activity(db_path: str | Path, activity_id: int) -> dict[str, Any]:
    activities = list_activities(db_path)
    for activity in activities:
        if activity["id"] == activity_id:
            return activity
    raise NotFoundError("アクティビティが見つかりませんでした。")


def _group_items(connection: sqlite3.Connection, table: str) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    columns = "id, activity_id, name, created_at"
    if table == "members":
        columns = "id, activity_id, name, email, created_at"
    rows = connection.execute(
        f"SELECT {columns} FROM {table} ORDER BY id ASC"
    ).fetchall()

    for row in rows:
        item = dict(row)
        activity_id = item.pop("activity_id")
        grouped.setdefault(activity_id, []).append(item)

    return grouped


def _group_assignments(connection: sqlite3.Connection) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    rows = connection.execute(
        """
        SELECT id, activity_id, role_id, member_id, assigned_on, created_at
        FROM role_assignments
        ORDER BY assigned_on DESC, id ASC
        """
    ).fetchall()

    for row in rows:
        assignment = dict(row)
        activity_id = assignment["activity_id"]
        grouped.setdefault(activity_id, []).append(assignment)

    return grouped


def _group_role_member_skips(
    connection: sqlite3.Connection,
) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    rows = connection.execute(
        """
        SELECT id, activity_id, role_id, member_id, skip_type, created_at
        FROM role_member_skips
        ORDER BY id ASC
        """
    ).fetchall()

    for row in rows:
        skip = dict(row)
        activity_id = skip["activity_id"]
        grouped.setdefault(activity_id, []).append(skip)

    return grouped


def _delete_activity_item(
    db_path: str | Path, table: str, activity_id: int, item_id: int
) -> None:
    with connect(db_path) as connection:
        cursor = connection.execute(
            f"DELETE FROM {table} WHERE id = ? AND activity_id = ?",
            (item_id, activity_id),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("項目が見つかりませんでした。")


def _require_activity(connection: sqlite3.Connection, activity_id: int) -> None:
    activity = connection.execute(
        "SELECT id FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if activity is None:
        raise NotFoundError("アクティビティが見つかりませんでした。")


def _require_activity_item(
    connection: sqlite3.Connection,
    table: str,
    activity_id: int,
    item_id: int,
    error_message: str,
) -> None:
    item = connection.execute(
        f"SELECT id FROM {table} WHERE id = ? AND activity_id = ?",
        (item_id, activity_id),
    ).fetchone()
    if item is None:
        raise NotFoundError(error_message)


def _item_exists(
    connection: sqlite3.Connection, table: str, activity_id: int, column: str, value: str
) -> bool:
    row = connection.execute(
        f"SELECT id FROM {table} WHERE activity_id = ? AND {column} = ? LIMIT 1",
        (activity_id, value),
    ).fetchone()
    return row is not None


def _item_count(connection: sqlite3.Connection, table: str, activity_id: int) -> int:
    row = connection.execute(
        f"SELECT COUNT(*) AS count FROM {table} WHERE activity_id = ?",
        (activity_id,),
    ).fetchone()
    return int(row["count"])


def _assignment_exists(
    connection: sqlite3.Connection, activity_id: int, role_id: int, assigned_on: str
) -> bool:
    row = connection.execute(
        """
        SELECT id
        FROM role_assignments
        WHERE activity_id = ? AND role_id = ? AND assigned_on = ?
        """,
        (activity_id, role_id, assigned_on),
    ).fetchone()
    return row is not None


def _next_member_id_for_rotation(
    connection: sqlite3.Connection,
    activity_id: int,
    role_id: int,
    member_ids: list[int],
    current_member_id: int,
) -> int | None:
    try:
        current_index = member_ids.index(current_member_id)
    except ValueError:
        current_index = -1

    for offset in range(1, len(member_ids) + 1):
        candidate = member_ids[(current_index + offset) % len(member_ids)]
        if _skip_role_member_for_rotation(connection, activity_id, role_id, candidate):
            continue
        return candidate
    return None


def _skip_role_member_for_rotation(
    connection: sqlite3.Connection, activity_id: int, role_id: int, member_id: int
) -> bool:
    skip = connection.execute(
        """
        SELECT id, skip_type
        FROM role_member_skips
        WHERE activity_id = ? AND role_id = ? AND member_id = ?
        """,
        (activity_id, role_id, member_id),
    ).fetchone()
    if skip is None:
        return False

    if skip["skip_type"] == SKIP_TYPE_ONCE:
        connection.execute(
            "DELETE FROM role_member_skips WHERE id = ?",
            (skip["id"],),
        )
    return True


def _is_role_member_skipped(
    connection: sqlite3.Connection, activity_id: int, role_id: int, member_id: int
) -> bool:
    row = connection.execute(
        """
        SELECT id
        FROM role_member_skips
        WHERE activity_id = ? AND role_id = ? AND member_id = ?
        """,
        (activity_id, role_id, member_id),
    ).fetchone()
    return row is not None


def _clean_skip_type(value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError("スキップ種別は文字列で入力してください。")
    cleaned = value.strip()
    if cleaned not in VALID_SKIP_TYPES:
        raise ValidationError("スキップ種別が正しくありません。")
    return cleaned


def _clean_assigned_on(value: str | None) -> str:
    if value is None:
        return date.today().isoformat()

    cleaned = value.strip()
    if not cleaned:
        raise ValidationError("担当日は必須です。")

    try:
        date.fromisoformat(cleaned)
    except ValueError as error:
        raise ValidationError("担当日はYYYY-MM-DD形式の正しい日付を入力してください。") from error
    return cleaned


def current_timestamp_ms() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
