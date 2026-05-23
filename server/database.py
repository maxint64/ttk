from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any


def connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: str | Path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
                UNIQUE (activity_id, name)
            );

            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
                UNIQUE (activity_id, email)
            );

            CREATE TABLE IF NOT EXISTS role_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                assigned_on TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
                UNIQUE (activity_id, role_id, member_id, assigned_on)
            );
            """
        )
        _migrate_members_email(connection)
        _create_unique_index_if_possible(
            connection,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS roles_activity_name_unique
            ON roles (activity_id, name)
            """,
        )
        _create_unique_index_if_possible(
            connection,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS members_activity_email_unique
            ON members (activity_id, email)
            WHERE email IS NOT NULL
            """,
        )


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

    for activity in activities:
        activity["roles"] = roles.get(activity["id"], [])
        activity["members"] = members.get(activity["id"], [])
        activity["assignments"] = assignments.get(activity["id"], [])

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
            raise NotFoundError("activity not found")


def add_role(db_path: str | Path, activity_id: int, name: str) -> dict[str, Any]:
    with connect(db_path) as connection:
        _require_activity(connection, activity_id)
        if _item_exists(connection, "roles", activity_id, "name", name):
            raise ValidationError("role already exists in this activity")

        try:
            cursor = connection.execute(
                "INSERT INTO roles (activity_id, name) VALUES (?, ?)",
                (activity_id, name),
            )
        except sqlite3.IntegrityError as error:
            raise ValidationError("role already exists in this activity") from error

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
            raise ValidationError("email already exists in this activity")

        try:
            cursor = connection.execute(
                "INSERT INTO members (activity_id, name, email) VALUES (?, ?, ?)",
                (activity_id, name, email),
            )
        except sqlite3.IntegrityError as error:
            raise ValidationError("email already exists in this activity") from error

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


def list_assignments(db_path: str | Path, activity_id: int) -> list[dict[str, Any]]:
    with connect(db_path) as connection:
        _require_activity(connection, activity_id)
        return _group_assignments(connection).get(activity_id, [])


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
            connection, "roles", activity_id, role_id, "role not found"
        )
        _require_activity_item(
            connection, "members", activity_id, member_id, "member not found"
        )

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
                (activity_id, role_id, member_id, assigned_on)
            VALUES (?, ?, ?, ?)
            """,
            (activity_id, role_id, member_id, assigned_on),
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

            next_member_id = _next_member_id(member_ids, latest["member_id"])
            cursor = connection.execute(
                """
                INSERT INTO role_assignments
                    (activity_id, role_id, member_id, assigned_on)
                VALUES (?, ?, ?, ?)
                """,
                (activity_id, role_id, next_member_id, target_on),
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


def delete_assignment(db_path: str | Path, activity_id: int, assignment_id: int) -> None:
    with connect(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM role_assignments WHERE id = ? AND activity_id = ?",
            (assignment_id, activity_id),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("assignment not found")


def get_activity(db_path: str | Path, activity_id: int) -> dict[str, Any]:
    activities = list_activities(db_path)
    for activity in activities:
        if activity["id"] == activity_id:
            return activity
    raise NotFoundError("activity not found")


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


def _delete_activity_item(
    db_path: str | Path, table: str, activity_id: int, item_id: int
) -> None:
    with connect(db_path) as connection:
        cursor = connection.execute(
            f"DELETE FROM {table} WHERE id = ? AND activity_id = ?",
            (item_id, activity_id),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("item not found")


def _require_activity(connection: sqlite3.Connection, activity_id: int) -> None:
    activity = connection.execute(
        "SELECT id FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if activity is None:
        raise NotFoundError("activity not found")


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


def _next_member_id(member_ids: list[int], current_member_id: int) -> int:
    try:
        current_index = member_ids.index(current_member_id)
    except ValueError:
        return member_ids[0]
    return member_ids[(current_index + 1) % len(member_ids)]


def _clean_assigned_on(value: str | None) -> str:
    if value is None:
        return date.today().isoformat()

    cleaned = value.strip()
    if not cleaned:
        raise ValidationError("assigned_on is required")

    try:
        date.fromisoformat(cleaned)
    except ValueError as error:
        raise ValidationError("assigned_on must be a valid YYYY-MM-DD date") from error
    return cleaned


def _migrate_members_email(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(members)").fetchall()
    }
    if "email" not in columns:
        connection.execute("ALTER TABLE members ADD COLUMN email TEXT")


def _create_unique_index_if_possible(
    connection: sqlite3.Connection, statement: str
) -> None:
    try:
        connection.execute(statement)
    except sqlite3.IntegrityError:
        pass
