from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Awaitable, Callable

from . import database
from .config import DEFAULT_DB_PATH


async def run_daily_rotation(
    db_path: str | Path = DEFAULT_DB_PATH,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    db_path = Path(db_path)
    database.init_db(db_path)

    while True:
        await sleep(seconds_until_next_midnight())
        created = database.rotate_assignments(db_path)
        if created:
            print(f"rotated {len(created)} assignments", flush=True)


def seconds_until_next_midnight(now: datetime | None = None) -> float:
    now = now or datetime.now()
    tomorrow = now.date() + timedelta(days=1)
    next_midnight = datetime.combine(tomorrow, time.min, tzinfo=now.tzinfo)
    return (next_midnight - now).total_seconds()
