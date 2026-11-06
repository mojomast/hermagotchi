"""Moderated text chat storage and read helpers.

Rows are plain text. No HTML/Markdown is rendered or interpreted by the server,
and nothing here feeds chat into an agent prompt.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from .. import CONTRACTS_VERSION
from .blocks import blocked_account_ids, is_blocked_either_way
from .errors import (
    BlockedInteraction,
    EmptyMessage,
    InvalidChannel,
    MessageTooLong,
    RateLimited,
)
from .sanitize import MAX_MESSAGE_CHARS, sanitize_display_text

_CHANNEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_ACTOR_MODES = frozenset({"human", "agent"})
_RATE_LIMITS = {
    "human": (5, 60),
    "agent": (2, 24 * 60 * 60),
}


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_channel(channel_id: str) -> str:
    text = (channel_id or "").strip()
    if not _CHANNEL_RE.match(text):
        raise InvalidChannel("Channel ids are 1-64 safe characters.")
    return text


def _direct_participants(channel_id: str) -> set[str] | None:
    for prefix in ("dm:", "direct:"):
        if channel_id.startswith(prefix):
            parts = [part for part in channel_id[len(prefix) :].split(":") if part]
            if len(parts) == 2:
                return set(parts)
    return None


def _check_rate_limit(
    conn: sqlite3.Connection, account_id: str, actor_mode: str, now: datetime
) -> None:
    limit, window_s = _RATE_LIMITS[actor_mode]
    window_start = _iso(now - timedelta(seconds=window_s))
    row = conn.execute(
        """
        SELECT COUNT(*) AS n, MIN(created_at) AS oldest
        FROM chats
        WHERE account_id = ? AND created_at >= ? AND deleted_at IS NULL
        """,
        (account_id, window_start),
    ).fetchone()
    if row["n"] < limit:
        return

    retry_after_s = window_s
    oldest = _parse_ts(row["oldest"] or "")
    if oldest is not None:
        expires = oldest + timedelta(seconds=window_s)
        retry_after_s = max(1, int((expires - now).total_seconds()) + 1)
    raise RateLimited(
        "Too many messages; wait before sending again.",
        retry_after_s=retry_after_s,
    )


def message_payload(row: sqlite3.Row) -> dict[str, object]:
    return {
        "contracts_version": CONTRACTS_VERSION,
        "id": row["id"],
        "channel_id": row["channel_id"],
        "account_id": row["account_id"],
        "actor_mode": row["actor_mode"],
        "body": row["body"],
        "created_at": row["created_at"],
        "deleted_at": row["deleted_at"],
    }


def send_message(
    conn: sqlite3.Connection,
    channel_id: str,
    account_id: str,
    body: object,
    *,
    actor_mode: str = "human",
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    channel = validate_channel(channel_id)
    mode = actor_mode if actor_mode in _ACTOR_MODES else "human"

    if idempotency_key:
        existing = conn.execute(
            "SELECT * FROM chats WHERE account_id = ? AND idempotency_key = ?",
            (account_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            return message_payload(existing)

    try:
        cleaned = sanitize_display_text(body, max_chars=MAX_MESSAGE_CHARS)
    except ValueError as exc:
        if str(exc) == "empty":
            raise EmptyMessage("Message body cannot be empty.") from exc
        raise MessageTooLong(
            f"Message body cannot exceed {MAX_MESSAGE_CHARS} characters."
        ) from exc

    participants = _direct_participants(channel)
    if participants and account_id in participants:
        for other in participants - {account_id}:
            if is_blocked_either_way(conn, account_id, other):
                raise BlockedInteraction("That conversation is blocked.")

    current = _now(now)
    _check_rate_limit(conn, account_id, mode, current)

    message_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO chats (
            id, channel_id, account_id, actor_mode, body,
            idempotency_key, created_at, deleted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (message_id, channel, account_id, mode, cleaned, idempotency_key, _iso(current)),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM chats WHERE id = ?", (message_id,)).fetchone()
    return message_payload(row)


def list_messages(
    conn: sqlite3.Connection,
    channel_id: str,
    *,
    viewer_id: str | None = None,
    limit: int = 50,
    before: str | None = None,
) -> tuple[list[dict[str, object]], str | None]:
    channel = validate_channel(channel_id)
    capped = max(1, min(int(limit), 100))

    sql = "SELECT * FROM chats WHERE channel_id = ? AND deleted_at IS NULL"
    params: list[object] = [channel]

    if viewer_id:
        blocked = blocked_account_ids(conn, viewer_id)
        if blocked:
            placeholders = ", ".join("?" for _ in blocked)
            sql += f" AND account_id NOT IN ({placeholders})"
            params.extend(sorted(blocked))

    if before:
        sql += " AND created_at < ?"
        params.append(before)

    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(capped)
    rows = conn.execute(sql, params).fetchall()

    messages = [message_payload(row) for row in reversed(rows)]
    next_before = messages[0]["created_at"] if len(messages) == capped else None
    return messages, next_before
