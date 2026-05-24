from __future__ import annotations

from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SERVER_ROOT.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "ttk.sqlite3"
DEFAULT_PID_PATH = PROJECT_ROOT / "data" / "ttk.pid"
DEFAULT_STATIC_DIR = PROJECT_ROOT / "app"
