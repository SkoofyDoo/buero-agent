"""Simple SQLite queue for Hermes → Telegram messages."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "queue.db"

STATUS_NEW = "new"
STATUS_PROCESSED = "processed"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the queue table if it does not exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT NOT NULL,
                data TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def add_to_queue(email_id: str, data: dict[str, Any] | str) -> int:
    """Insert a new item into the queue. Returns the new row id."""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    created_at = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO queue (email_id, data, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (email_id, payload, STATUS_NEW, created_at),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_new_items() -> list[dict[str, Any]]:
    """Return all items with status 'new', oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, email_id, data, status, created_at
            FROM queue
            WHERE status = ?
            ORDER BY id ASC
            """,
            (STATUS_NEW,),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            item["data"] = json.loads(item["data"])
        except (json.JSONDecodeError, TypeError):
            pass
        items.append(item)
    return items


def mark_as_processed(item_id: int) -> None:
    """Mark a queue item as processed."""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE queue
            SET status = ?
            WHERE id = ?
            """,
            (STATUS_PROCESSED, item_id),
        )
        conn.commit()
