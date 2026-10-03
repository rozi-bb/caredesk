"""Operational database of the nursing home."""

import os
import sqlite3
from datetime import date
from pathlib import Path

# "Today" inside the synthetic data. Fixed so that answers about "today"
# do not change from one day to the next and evaluations stay comparable.
REFERENCE_DATE = date(2026, 10, 5)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def db_path() -> Path:
    """Return the database file, from CAREDESK_DB_PATH or the default location."""
    return Path(os.environ.get("CAREDESK_DB_PATH", "data/caredesk.db"))


def connect_readonly() -> sqlite3.Connection:
    """Open the database read-only, so tools cannot change data even by mistake."""
    path = db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found at {path}. Build it with: uv run python scripts/seed_db.py"
        )
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
