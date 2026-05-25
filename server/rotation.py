from __future__ import annotations

from pathlib import Path
from typing import Any

from . import database, events
from .config import DEFAULT_DB_PATH


def rotate_once(
    db_path: str | Path = DEFAULT_DB_PATH,
    target_on: str | None = None,
) -> list[dict[str, Any]]:
    db_path = Path(db_path)
    database.init_db(db_path)
    return database.rotate_assignments(db_path, target_on)


def run(db_path: str | Path = DEFAULT_DB_PATH, target_on: str | None = None) -> None:
    created = rotate_once(db_path, target_on)
    if created:
        events.publish_assignments_changed(
            len(created),
            assigned_on=created[0]["assigned_on"],
            activity_ids=sorted({item["activity_id"] for item in created}),
        )
    print(f"rotated {len(created)} assignments", flush=True)
    for assignment in database.describe_assignments(
        db_path, [item["id"] for item in created]
    ):
        print(
            (
                f"{assignment['assigned_on']} "
                f"{assignment['activity_name']} / {assignment['role_name']} -> "
                f"{assignment['member_name']} <{assignment['member_email']}>"
            ),
            flush=True,
        )
