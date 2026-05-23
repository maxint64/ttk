import os
from pathlib import Path

from server.config import DEFAULT_DB_PATH
from server.rotation import run


if __name__ == "__main__":
    db_path = Path(os.environ.get("TTK_DB_PATH", DEFAULT_DB_PATH))
    run(db_path)
