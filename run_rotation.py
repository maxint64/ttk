import os
from pathlib import Path

from ttk_backend.config import DEFAULT_DB_PATH
from ttk_backend.rotation import run


if __name__ == "__main__":
    db_path = Path(os.environ.get("TTK_DB_PATH", DEFAULT_DB_PATH))
    run(db_path)
