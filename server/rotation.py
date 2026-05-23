from __future__ import annotations

from pathlib import Path
from typing import Any

from . import database
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
    print(f"rotated {len(created)} assignments", flush=True)
