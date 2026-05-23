from __future__ import annotations

import sqlite3
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
                FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
            );
            """
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

    for activity in activities:
        activity["roles"] = roles.get(activity["id"], [])
        activity["members"] = members.get(activity["id"], [])

    return activities


def create_activity(db_path: str | Path, name: str) -> dict[str, Any]:
    name = _clean_name(name)
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
    return _add_activity_item(db_path, "roles", activity_id, name)


def add_member(db_path: str | Path, activity_id: int, name: str) -> dict[str, Any]:
    return _add_activity_item(db_path, "members", activity_id, name)


def delete_role(db_path: str | Path, activity_id: int, role_id: int) -> None:
    _delete_activity_item(db_path, "roles", activity_id, role_id)


def delete_member(db_path: str | Path, activity_id: int, member_id: int) -> None:
    _delete_activity_item(db_path, "members", activity_id, member_id)


def get_activity(db_path: str | Path, activity_id: int) -> dict[str, Any]:
    activities = list_activities(db_path)
    for activity in activities:
        if activity["id"] == activity_id:
            return activity
    raise NotFoundError("activity not found")


def _group_items(connection: sqlite3.Connection, table: str) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    rows = connection.execute(
        f"SELECT id, activity_id, name, created_at FROM {table} ORDER BY id ASC"
    ).fetchall()

    for row in rows:
        item = dict(row)
        activity_id = item.pop("activity_id")
        grouped.setdefault(activity_id, []).append(item)

    return grouped


def _add_activity_item(
    db_path: str | Path, table: str, activity_id: int, name: str
) -> dict[str, Any]:
    name = _clean_name(name)
    with connect(db_path) as connection:
        activity = connection.execute(
            "SELECT id FROM activities WHERE id = ?", (activity_id,)
        ).fetchone()
        if activity is None:
            raise NotFoundError("activity not found")

        cursor = connection.execute(
            f"INSERT INTO {table} (activity_id, name) VALUES (?, ?)",
            (activity_id, name),
        )
        item_id = cursor.lastrowid
        row = connection.execute(
            f"SELECT id, name, created_at FROM {table} WHERE id = ?", (item_id,)
        ).fetchone()

    return dict(row)


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


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValidationError("name is required")
    if len(cleaned) > 120:
        raise ValidationError("name must be 120 characters or fewer")
    return cleaned

