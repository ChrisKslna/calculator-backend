"""SQLite history storage; each request owns and closes its connection."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


@contextmanager
def connect(database):
    connection = sqlite3.connect(database, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize(database):
    """Create the table without clearing existing history."""
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    with connect(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS calculation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expression TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def save_calculation(database, expression, result):
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect(database) as connection:
        cursor = connection.execute(
            "INSERT INTO calculation_history "
            "(expression, result, created_at) VALUES (?, ?, ?)",
            (expression, result, created_at),
        )
        return {
            "id": cursor.lastrowid,
            "expression": expression,
            "result": result,
            "created_at": created_at,
        }


def list_history(database, page, page_size):
    with connect(database) as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM calculation_history"
        ).fetchone()[0]
        pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, pages)
        rows = connection.execute(
            "SELECT id, expression, result, created_at "
            "FROM calculation_history ORDER BY id DESC LIMIT ? OFFSET ?",
            (page_size, (page - 1) * page_size),
        ).fetchall()
        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }


def delete_calculation(database, record_id):
    with connect(database) as connection:
        cursor = connection.execute(
            "DELETE FROM calculation_history WHERE id = ?", (record_id,)
        )
        return cursor.rowcount == 1
