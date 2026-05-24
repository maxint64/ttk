from __future__ import annotations

from pathlib import Path

from . import database
from .config import DEFAULT_DB_PATH


def reset_and_seed(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()

    database.init_db(db_path)

    standup = database.create_activity(db_path, "朝会")
    tanaka = database.add_member(db_path, standup["id"], "田中", "tanaka@example.com")
    sato = database.add_member(db_path, standup["id"], "佐藤", "sato@example.com")
    suzuki = database.add_member(db_path, standup["id"], "鈴木", "suzuki@example.com")
    facilitator = database.add_role(db_path, standup["id"], "司会")
    note_taker = database.add_role(db_path, standup["id"], "記録")
    database.add_assignment(
        db_path, standup["id"], facilitator["id"], tanaka["id"], "2026-05-22"
    )
    database.add_assignment(
        db_path, standup["id"], note_taker["id"], sato["id"], "2026-05-22"
    )
    database.add_assignment(
        db_path, standup["id"], facilitator["id"], sato["id"], "2026-05-23"
    )
    database.add_assignment(
        db_path, standup["id"], note_taker["id"], suzuki["id"], "2026-05-23"
    )

    cleanup = database.create_activity(db_path, "掃除当番")
    yamada = database.add_member(db_path, cleanup["id"], "山田", "yamada@example.com")
    ito = database.add_member(db_path, cleanup["id"], "伊藤", "ito@example.com")
    floor = database.add_role(db_path, cleanup["id"], "床")
    trash = database.add_role(db_path, cleanup["id"], "ゴミ出し")
    database.add_assignment(
        db_path, cleanup["id"], floor["id"], yamada["id"], "2026-05-23"
    )
    database.add_assignment(
        db_path, cleanup["id"], trash["id"], ito["id"], "2026-05-23"
    )

    print(f"seeded database at {db_path}")


if __name__ == "__main__":
    reset_and_seed()
