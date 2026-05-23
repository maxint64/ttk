import argparse
import os
from datetime import date
from pathlib import Path

from server.config import DEFAULT_DB_PATH
from server.rotation import run


def valid_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "date must be a valid YYYY-MM-DD date"
        ) from error
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run assignment rotation once.")
    parser.add_argument(
        "--date",
        dest="target_on",
        type=valid_date,
        help="Target assignment date in YYYY-MM-DD format. Defaults to today.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    db_path = Path(os.environ.get("TTK_DB_PATH", DEFAULT_DB_PATH))
    run(db_path, args.target_on)
