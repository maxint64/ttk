from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "data" / "ttk.sqlite3"
DEFAULT_STATIC_DIR = ROOT
