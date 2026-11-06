"""Per-account block list helpers.

Blocks are symmetric for visibility: if either side blocks the other, messages
from the blocked account are filtered from reads and direct-message sends are
refused.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..db import account_exists
from .errors import InvalidTarget


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def block_account(
    conn: sqlite3.Connection,
    blocker_id: str,
    blocked_id: str,
    now: datetime | None = None,
) -> dict[str, object]:
    if blocker_id == blocked_id:
        raise InvalidTarget("An account cannot block itself.")
    if not account_exists(conn, blocked_id):
        raise InvalidTarget("No active account exists for that id.")

    timestamp = _now(now).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    conn.execute(
        """
        INSERT OR IGNORE INTO blocks (blocker_id, blocked_id, created_at)
        VALUES (?, ?, ?)
        """,
        (blocker_id, blocked_id, timestamp),
    )
    row = conn.execute(
        "SELECT * FROM blocks WHERE blocker_id = ? AND blocked_id = ?",
        (blocker_id, blocked_id),
    ).fetchone()
    conn.commit()
    return {
        "blocker_id": row["blocker_id"],
        "blocked_id": row["blocked_id"],
        "created_at": row["created_at"],
        "blocked": True,
    }


def unblock_account(
    conn: sqlite3.Connection,
    blocker_id: str,
    blocked_id: str,
) -> bool:
    cursor = conn.execute(
        "DELETE FROM blocks WHERE blocker_id = ? AND blocked_id = ?",
        (blocker_id, blocked_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def is_blocked(conn: sqlite3.Connection, blocker_id: str, blocked_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM blocks WHERE blocker_id = ? AND blocked_id = ?",
        (blocker_id, blocked_id),
    ).fetchone()
    return row is not None


def is_blocked_either_way(
    conn: sqlite3.Connection, account_a: str, account_b: str
) -> bool:
    return is_blocked(conn, account_a, account_b) or is_blocked(
        conn, account_b, account_a
    )


def blocked_account_ids(conn: sqlite3.Connection, account_id: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT blocked_id AS other FROM blocks WHERE blocker_id = ?
        UNION
        SELECT blocker_id AS other FROM blocks WHERE blocked_id = ?
        """,
        (account_id, account_id),
    ).fetchall()
    return {row["other"] for row in rows}


def list_blocks(conn: sqlite3.Connection, account_id: str) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT blocked_id, created_at FROM blocks WHERE blocker_id = ? "
        "ORDER BY created_at, blocked_id",
        (account_id,),
    ).fetchall()
    return [
        {"blocked_id": row["blocked_id"], "created_at": row["created_at"]}
        for row in rows
    ]
