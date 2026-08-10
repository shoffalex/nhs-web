"""SQLite access via the stdlib `sqlite3` module — no ORM.

Each request gets its own connection from the `get_db` dependency. WAL lets
the public read events while you're editing in the admin page, and
busy_timeout makes a second concurrent write wait its turn instead of failing
with "database is locked".
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from .config import get_settings

# The schema lives in SQL, not Python: migrations/001_init.sql is both the
# reference and what actually creates the tables.
_SCHEMA_FILE = Path(__file__).resolve().parents[1] / "migrations" / "001_init.sql"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    """Create missing tables. Runs at startup; the SQL is all IF NOT EXISTS."""
    conn = connect()
    try:
        conn.executescript(_SCHEMA_FILE.read_text())
        conn.commit()
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
