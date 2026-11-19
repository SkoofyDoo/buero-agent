"""SQLite queue: stores Hermes JSON, returns EmailData."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bot.config import EmailData

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "queue.db"

STATUS_NEW = "new"
STATUS_PROCESSED = "processed"


@dataclass
class QueueItem:
    id: int
    email_id: str
    email: EmailData
    status: str
    created_at: str
    raw: dict[str, Any]


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_payload(data: EmailData | dict[str, Any] | str) -> dict[str, Any]:
    """Turn EmailData / dict / JSON string into a plain dict."""
    if isinstance(data, EmailData):
        return data.to_dict()
    if isinstance(data, str):
        return json.loads(data)
    return dict(data)


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


def add_to_queue(
    data: EmailData | dict[str, Any] | str,
    email_id: str | None = None,
) -> int:
    """
    Store Hermes JSON in the queue.

    Accepts EmailData, dict, or JSON string.
    Returns the new row id.
    """
    payload = _normalize_payload(data)
    resolved_id = email_id or str(payload.get("email_id") or "")
    if not resolved_id:
        raise ValueError("email_id is required")

    payload["email_id"] = resolved_id
    created_at = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO queue (email_id, data, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                resolved_id,
                json.dumps(payload, ensure_ascii=False),
                STATUS_NEW,
                created_at,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_new_items() -> list[QueueItem]:
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

    items: list[QueueItem] = []
    for row in rows:
        raw = json.loads(row["data"])
        email = EmailData.from_dict(raw)
        items.append(
            QueueItem(
                id=row["id"],
                email_id=row["email_id"],
                email=email,
                status=row["status"],
                created_at=row["created_at"],
                raw=raw,
            )
        )
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
