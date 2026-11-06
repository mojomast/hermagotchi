"""Friend requests, friendships, presence and cross-channel social history.

Friendships are stored in both directions so a lookup is a single indexed
read. Requests are forward-only rows; accepting one writes the symmetric
``friendships`` rows inside the same transaction.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from ..db import account_exists
from .blocks import is_blocked_either_way
from .chat import message_payload
from .errors import (
    FriendAlready,
    FriendBlocked,
    FriendNotFound,
    FriendPending,
    FriendSelf,
    InvalidHistoryFilter,
    InvalidTarget,
)

PRESENCE_ONLINE_S = 120
PRESENCE_AWAY_S = 900

HISTORY_FILTERS = frozenset(
    {"all", "taunts_sent", "taunts_received", "mentions"}
)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def presence_bucket(last_seen_at: str | None, now: datetime | None = None) -> str:
    """Return ``online`` (<2 min), ``away`` (<15 min) or ``offline`` (UTC)."""

    seen = _parse_ts(last_seen_at)
    if seen is None:
        return "offline"
    age = (_now(now) - seen).total_seconds()
    if age < 0:
        age = 0
    if age < PRESENCE_ONLINE_S:
        return "online"
    if age < PRESENCE_AWAY_S:
        return "away"
    return "offline"


def touch_presence(
    conn: sqlite3.Connection,
    account_id: str,
    now: datetime | None = None,
) -> dict[str, object]:
    if not account_exists(conn, account_id):
        raise FriendNotFound("No active account exists for that id.")
    stamp = _iso(_now(now))
    conn.execute(
        """
        INSERT INTO account_presence (account_id, last_seen_at)
        VALUES (?, ?)
        ON CONFLICT(account_id) DO UPDATE SET
            last_seen_at = excluded.last_seen_at
        """,
        (account_id, stamp),
    )
    conn.commit()
    return {
        "account_id": account_id,
        "last_seen_at": stamp,
        "presence": presence_bucket(stamp, now),
    }


def get_presence(
    conn: sqlite3.Connection,
    account_id: str,
    now: datetime | None = None,
) -> dict[str, object]:
    row = conn.execute(
        "SELECT last_seen_at FROM account_presence WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    last_seen_at = row["last_seen_at"] if row is not None else None
    return {
        "account_id": account_id,
        "last_seen_at": last_seen_at,
        "presence": presence_bucket(last_seen_at, now),
    }


def _request_payload(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "from_account_id": row["from_account_id"],
        "to_account_id": row["to_account_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "resolved_at": row["resolved_at"],
    }


def _pending_between(
    conn: sqlite3.Connection, account_a: str, account_b: str
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM friend_requests
        WHERE status = 'pending'
          AND (
            (from_account_id = ? AND to_account_id = ?)
            OR (from_account_id = ? AND to_account_id = ?)
          )
        ORDER BY created_at DESC LIMIT 1
        """,
        (account_a, account_b, account_b, account_a),
    ).fetchone()


def _are_friends(
    conn: sqlite3.Connection, account_a: str, account_b: str
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM friendships WHERE account_id = ? AND friend_id = ?",
        (account_a, account_b),
    ).fetchone()
    return row is not None


def send_friend_request(
    conn: sqlite3.Connection,
    from_account_id: str,
    to_account_id: str,
    now: datetime | None = None,
) -> dict[str, object]:
    sender = str(from_account_id)
    recipient = str(to_account_id)
    if sender == recipient:
        raise FriendSelf("An account cannot friend itself.")
    if not account_exists(conn, recipient):
        raise FriendNotFound("No active account exists for that id.")
    if is_blocked_either_way(conn, sender, recipient):
        raise FriendBlocked("Friend requests are blocked between these accounts.")
    if _are_friends(conn, sender, recipient) or _are_friends(
        conn, recipient, sender
    ):
        raise FriendAlready("These accounts are already friends.")
    if _pending_between(conn, sender, recipient) is not None:
        raise FriendPending("A friend request is already pending.")

    request_id = str(uuid.uuid4())
    stamp = _iso(_now(now))
    conn.execute(
        """
        INSERT INTO friend_requests (
            id, from_account_id, to_account_id, status, created_at, resolved_at
        ) VALUES (?, ?, ?, 'pending', ?, NULL)
        """,
        (request_id, sender, recipient, stamp),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM friend_requests WHERE id = ?", (request_id,)
    ).fetchone()
    return _request_payload(row)


def respond_friend_request(
    conn: sqlite3.Connection,
    account_id: str,
    request_id: str,
    action: str,
    now: datetime | None = None,
) -> dict[str, object]:
    row = conn.execute(
        "SELECT * FROM friend_requests WHERE id = ?", (str(request_id),)
    ).fetchone()
    if row is None or str(row["to_account_id"]) != str(account_id):
        raise FriendNotFound("No pending friend request exists for that id.")
    if row["status"] == "accepted":
        raise FriendAlready("That friend request was already accepted.")
    if row["status"] != "pending":
        raise FriendNotFound("That friend request is no longer pending.")

    normalized = (action or "").strip().lower()
    if normalized in {"accept", "accepted"}:
        status = "accepted"
    elif normalized in {"decline", "declined"}:
        status = "declined"
    else:
        raise InvalidTarget("action must be 'accept' or 'decline'.")

    sender = str(row["from_account_id"])
    if is_blocked_either_way(conn, account_id, sender):
        raise FriendBlocked("Friend requests are blocked between these accounts.")

    timestamp = _iso(_now(now))
    conn.execute(
        """
        UPDATE friend_requests
        SET status = ?, resolved_at = ?
        WHERE id = ? AND status = 'pending'
        """,
        (status, timestamp, row["id"]),
    )
    if status == "accepted":
        conn.execute(
            """
            INSERT OR IGNORE INTO friendships (account_id, friend_id, created_at)
            VALUES (?, ?, ?), (?, ?, ?)
            """,
            (sender, str(account_id), timestamp, str(account_id), sender, timestamp),
        )
    conn.commit()
    updated = conn.execute(
        "SELECT * FROM friend_requests WHERE id = ?", (row["id"],)
    ).fetchone()
    return _request_payload(updated)


def accept_friend_request(
    conn: sqlite3.Connection,
    account_id: str,
    request_id: str,
    now: datetime | None = None,
) -> dict[str, object]:
    return respond_friend_request(conn, account_id, request_id, "accept", now=now)


def decline_friend_request(
    conn: sqlite3.Connection,
    account_id: str,
    request_id: str,
    now: datetime | None = None,
) -> dict[str, object]:
    return respond_friend_request(conn, account_id, request_id, "decline", now=now)


def remove_friend(
    conn: sqlite3.Connection,
    account_id: str,
    friend_id: str,
) -> dict[str, object]:
    if str(account_id) == str(friend_id):
        raise FriendSelf("An account cannot remove itself as a friend.")
    cursor = conn.execute(
        """
        DELETE FROM friendships
        WHERE (account_id = ? AND friend_id = ?)
           OR (account_id = ? AND friend_id = ?)
        """,
        (str(account_id), str(friend_id), str(friend_id), str(account_id)),
    )
    conn.commit()
    if cursor.rowcount == 0:
        raise FriendNotFound("These accounts are not friends.")
    return {
        "account_id": str(account_id),
        "friend_id": str(friend_id),
        "removed": True,
    }


def list_friends(
    conn: sqlite3.Connection,
    account_id: str,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
            f.friend_id AS friend_id,
            f.created_at AS friends_since,
            a.public_handle AS public_handle,
            p.last_seen_at AS last_seen_at
        FROM friendships AS f
        JOIN accounts AS a ON a.id = f.friend_id AND a.status = 'active'
        LEFT JOIN account_presence AS p ON p.account_id = f.friend_id
        WHERE f.account_id = ?
        ORDER BY f.created_at, f.friend_id
        """,
        (str(account_id),),
    ).fetchall()
    return [
        {
            "account_id": row["friend_id"],
            "friend_id": row["friend_id"],
            "public_handle": row["public_handle"],
            "friends_since": row["friends_since"],
            "last_seen_at": row["last_seen_at"],
            "presence": presence_bucket(row["last_seen_at"], now),
        }
        for row in rows
    ]


def list_friend_requests(
    conn: sqlite3.Connection,
    account_id: str,
    now: datetime | None = None,
) -> dict[str, list[dict[str, object]]]:
    incoming = conn.execute(
        """
        SELECT * FROM friend_requests
        WHERE to_account_id = ? AND status = 'pending'
        ORDER BY created_at DESC, id DESC
        """,
        (str(account_id),),
    ).fetchall()
    outgoing = conn.execute(
        """
        SELECT * FROM friend_requests
        WHERE from_account_id = ? AND status = 'pending'
        ORDER BY created_at DESC, id DESC
        """,
        (str(account_id),),
    ).fetchall()
    return {
        "incoming": [_request_payload(row) for row in incoming],
        "outgoing": [_request_payload(row) for row in outgoing],
    }


def list_social_history(
    conn: sqlite3.Connection,
    account_id: str,
    *,
    filter: str = "all",
    limit: int = 50,
    before: str | None = None,
) -> tuple[list[dict[str, object]], str | None]:
    """Return taunts/mentions relevant to the caller, newest first.

    Taunt entries carry ``match_id`` so clients can link to a replay.
    """

    name = (filter or "all").strip().lower()
    if name not in HISTORY_FILTERS:
        raise InvalidHistoryFilter(
            "filter must be all, taunts_sent, taunts_received or mentions."
        )
    capped = max(1, min(int(limit), 100))
    account = str(account_id)

    handle_row = conn.execute(
        "SELECT public_handle FROM accounts WHERE id = ?", (account,)
    ).fetchone()
    handle = str(handle_row["public_handle"]) if handle_row is not None else ""

    selects: list[str] = []
    params: list[object] = []

    if name in {"all", "taunts_sent"}:
        selects.append(
            "SELECT c.* FROM chats AS c WHERE c.deleted_at IS NULL "
            "AND c.kind = 'taunt' AND c.account_id = ?"
        )
        params.append(account)

    if name in {"all", "taunts_received"}:
        selects.append(
            """
            SELECT c.* FROM chats AS c
            WHERE c.deleted_at IS NULL AND c.kind = 'taunt' AND c.account_id <> ?
              AND (
                (
                  c.match_id IS NOT NULL AND c.match_id IN (
                    SELECT m.id FROM matches AS m
                    JOIN challenges AS ch ON ch.id = m.challenge_id
                    WHERE ch.challenger_id = ? OR ch.defender_id = ?
                  )
                )
                OR (
                  c.channel_id LIKE 'dm:%'
                  AND instr(c.channel_id, ?) > 0
                )
              )
            """
        )
        params.extend([account, account, account, account])

    if name in {"all", "mentions"} and handle:
        selects.append(
            "SELECT c.* FROM chats AS c WHERE c.deleted_at IS NULL "
            "AND c.account_id <> ? AND instr(lower(c.body), lower(?)) > 0"
        )
        params.extend([account, f"@{handle}"])

    if not selects:
        return [], None

    sql = "SELECT * FROM (" + " UNION ".join(selects) + ") AS h"
    if before:
        sql += " WHERE h.created_at < ?"
        params.append(before)
    sql += " ORDER BY h.created_at DESC, h.id DESC LIMIT ?"
    params.append(capped)

    rows = conn.execute(sql, params).fetchall()
    entries = [message_payload(row) for row in rows]
    next_before = entries[-1]["created_at"] if len(entries) == capped else None
    return entries, next_before

# Readable aliases for callers that mirror the route/operation names.
add_friend = send_friend_request
accept_friend = accept_friend_request
decline_friend = decline_friend_request
presence_status = presence_bucket
social_history = list_social_history
