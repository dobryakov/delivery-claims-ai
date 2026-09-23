"""SQLite connection helpers and database initialization.

The orders database is a deterministic mock (specs §3). `init_db` (re)builds it
from data/seed.sql so runs are reproducible.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.config import DATA_DIR, ORDERS_DB_PATH, ROOT_DIR

SEED_SQL_PATH = ROOT_DIR / "data" / "seed.sql"


def get_connection(db_path: Path = ORDERS_DB_PATH) -> sqlite3.Connection:
    """Open a connection with row access by column name."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = ORDERS_DB_PATH, seed_sql: Path = SEED_SQL_PATH) -> None:
    """(Re)create the orders database from the seed script."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    script = seed_sql.read_text(encoding="utf-8")
    conn = get_connection(db_path)
    try:
        conn.executescript(script)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Initialized orders database at {ORDERS_DB_PATH}")
