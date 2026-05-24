import os
from pathlib import Path

from server.config import DEFAULT_DB_PATH, DEFAULT_PID_PATH
from server.server import run


if __name__ == "__main__":
    host = os.environ.get("TTK_HOST", "127.0.0.1")
    port = int(os.environ.get("TTK_PORT", "8000"))
    db_path = Path(os.environ.get("TTK_DB_PATH", DEFAULT_DB_PATH))
    pid_path = Path(os.environ.get("TTK_PID_PATH", DEFAULT_PID_PATH))
    run(host=host, port=port, db_path=db_path, pid_path=pid_path)
