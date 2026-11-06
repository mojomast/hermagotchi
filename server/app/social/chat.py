"""Moderated text chat storage, DM inbox and taunt helpers.

Rows are plain text. No HTML/Markdown is rendered or interpreted by the server,
and nothing here feeds chat into an agent prompt.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from .. import CONTRACTS_VERSION
from .blocks import blocked_account_ids, is_blocked_either_way
from .errors import (
    AgentChatDisabled,
    ChatCooldown,
    ChatDailyCap,
    DMBlocked,
    DMCooldown,
    DMUnansweredCap,
    EmptyMessage,
    InvalidChannel,
    InvalidTarget,
    MessageTooLong,
    RateLimited,
    TauntInvalidMatch,
)
from .sanitize import MAX_MESSAGE_CHARS, sanitize_display_text

MAX_CHANNEL_CHARS = 128
MAX_TAUNT_CHARS = 120

LOBBY_CHANNEL = "lobby"
INBOX_CURSOR_CHANNEL = "inbox"

AGENT_LOBBY_DAILY_CAP = 20
AGENT_DM_DAILY_CAP = 10
AGENT_RECIPIENT_COOLDOWN_S = 60  # DMs only, per recipient channel
AGENT_LOBBY_COOLDOWN_S = 10  # lobby/taunt anti-spam; reason chat.cooldown
AGENT_UNANSWERED_DM_CAP = 2

_CHANNEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ACTOR_MODES = frozenset({"human", "agent"})
_RATE_LIMITS = {
    "human": (5, 60),
}
_TAUNT_PHASES = frozenset({"pre", "post"})


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
        raise InvalidChannel("Channel ids are 1-128 safe characters.")
    return text


def _direct_participants(channel_id: str) -> set[str] | None:
    for prefix in ("dm:", "direct:"):
        if channel_id.startswith(prefix):
            parts = [part for part in channel_id[len(prefix) :].split(":") if part]
            if len(parts) == 2:
                return set(parts)
    return None


def dm_channel_for(account_a: str, account_b: str) -> str:
    """Return the canonical sorted DM channel id for two accounts."""

    first, second = sorted((str(account_a), str(account_b)))
    return validate_channel(f"dm:{first}:{second}")


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def resolve_target_account(conn: sqlite3.Connection, target: object) -> str:
    """Resolve an account id, public handle or unique pet name to an account id."""

    if not isinstance(target, str):
        raise InvalidTarget("A valid target is required.")
    text = target.strip()
    if text.startswith("@"):
        text = text[1:].strip()
    if not text or len(text) > MAX_CHANNEL_CHARS:
        raise InvalidTarget("A valid target is required.")

    if _looks_like_uuid(text):
        normalized = str(uuid.UUID(text))
        row = conn.execute(
            "SELECT id FROM accounts WHERE id = ? AND status = 'active'",
            (normalized,),
        ).fetchone()
        if row is None:
            raise InvalidTarget("No active account exists for that target.")
        return str(row["id"])

    row = conn.execute(
        "SELECT id FROM accounts WHERE public_handle = ? AND status = 'active'",
        (text,),
    ).fetchone()
    if row is not None:
        return str(row["id"])

    case_rows = conn.execute(
        "SELECT id FROM accounts WHERE public_handle = ? COLLATE NOCASE "
        "AND status = 'active'",
        (text,),
    ).fetchall()
    if len(case_rows) == 1:
        return str(case_rows[0]["id"])
    if len(case_rows) > 1:
        raise InvalidTarget("That handle is ambiguous; use an account id.")

    rows = conn.execute(
        """
        SELECT p.account_id AS account_id
        FROM pets AS p
        JOIN accounts AS a ON a.id = p.account_id
        WHERE p.name = ? AND a.status = 'active'
        """,
        (text,),
    ).fetchall()
    if len(rows) == 1:
        return str(rows[0]["account_id"])
    if len(rows) > 1:
        raise InvalidTarget("That pet name is ambiguous; use an account id or handle.")
    raise InvalidTarget("No active account or pet exists for that target.")


def resolve_dm_channel(
    conn: sqlite3.Connection, sender_id: str, target: object
) -> str:
    """Resolve a player/pet target to the canonical ``dm:<a>:<b>`` channel."""

    resolved = resolve_target_account(conn, target)
    if resolved == str(sender_id):
        raise InvalidTarget("An account cannot direct-message itself.")
    return dm_channel_for(sender_id, resolved)


def get_chat_settings(
    conn: sqlite3.Connection, account_id: str
) -> dict[str, object]:
    row = conn.execute(
        "SELECT agent_chat_enabled, updated_at FROM account_chat_settings "
        "WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    enabled = bool(row["agent_chat_enabled"]) if row is not None else False
    return {
        "agent_chat_enabled": enabled,
        "chat_enabled": enabled,
        "updated_at": row["updated_at"] if row is not None else None,
    }


def set_agent_chat_enabled(
    conn: sqlite3.Connection,
    account_id: str,
    enabled: bool,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    stamp = _iso(_now(now))
    conn.execute(
        """
        INSERT INTO account_chat_settings (
            account_id, agent_chat_enabled, updated_at
        ) VALUES (?, ?, ?)
        ON CONFLICT(account_id) DO UPDATE SET
            agent_chat_enabled = excluded.agent_chat_enabled,
            updated_at = excluded.updated_at
        """,
        (account_id, 1 if enabled else 0, stamp),
    )
    conn.commit()
    return get_chat_settings(conn, account_id)


def _agent_chat_enabled(conn: sqlite3.Connection, account_id: str) -> bool:
    row = conn.execute(
        "SELECT agent_chat_enabled FROM account_chat_settings WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    return row is not None and bool(row["agent_chat_enabled"])


def _check_rate_limit(
    conn: sqlite3.Connection, account_id: str, actor_mode: str, now: datetime
) -> None:
    limit, window_s = _RATE_LIMITS.get(actor_mode, _RATE_LIMITS["human"])
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


def _day_start(now: datetime) -> datetime:
    return now.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _seconds_until_midnight(now: datetime) -> int:
    tomorrow = _day_start(now) + timedelta(days=1)
    return max(1, int(math.ceil((tomorrow - now).total_seconds())))


def _daily_count(
    conn: sqlite3.Connection, account_id: str, now: datetime, *, dm: bool
) -> int:
    start = _iso(_day_start(now))
    if dm:
        channel_clause = "(channel_id LIKE 'dm:%' OR channel_id LIKE 'direct:%')"
    else:
        channel_clause = "channel_id NOT LIKE 'dm:%' AND channel_id NOT LIKE 'direct:%'"
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS n FROM chats
        WHERE account_id = ? AND created_at >= ? AND deleted_at IS NULL
          AND {channel_clause}
        """,
        (account_id, start),
    ).fetchone()
    return int(row["n"])


def _last_outgoing_at(
    conn: sqlite3.Connection, account_id: str, channel_id: str, *, dm: bool
) -> datetime | None:
    if dm:
        sql = (
            "SELECT created_at FROM chats "
            "WHERE account_id = ? AND channel_id = ? AND deleted_at IS NULL "
            "ORDER BY created_at DESC, id DESC LIMIT 1"
        )
        params: tuple[object, ...] = (account_id, channel_id)
    else:
        sql = (
            "SELECT created_at FROM chats "
            "WHERE account_id = ? AND deleted_at IS NULL "
            "AND channel_id NOT LIKE 'dm:%' AND channel_id NOT LIKE 'direct:%' "
            "ORDER BY created_at DESC, id DESC LIMIT 1"
        )
        params = (account_id,)
    row = conn.execute(sql, params).fetchone()
    return _parse_ts(row["created_at"]) if row is not None else None


def _unanswered_dm_count(
    conn: sqlite3.Connection, account_id: str, channel_id: str, other_id: str
) -> int:
    rows = conn.execute(
        """
        SELECT account_id FROM chats
        WHERE channel_id = ? AND deleted_at IS NULL
        ORDER BY created_at DESC, id DESC LIMIT 100
        """,
        (channel_id,),
    ).fetchall()
    count = 0
    for row in rows:
        sender = str(row["account_id"])
        if sender == str(account_id):
            count += 1
        elif sender == str(other_id):
            break
    return count


def _enforce_agent_limits(
    conn: sqlite3.Connection,
    account_id: str,
    channel_id: str,
    now: datetime,
    *,
    other_id: str | None,
) -> None:
    if not _agent_chat_enabled(conn, account_id):
        raise AgentChatDisabled(
            "Agent chat is disabled; enable agent chat settings first."
        )

    dm = other_id is not None
    cap = AGENT_DM_DAILY_CAP if dm else AGENT_LOBBY_DAILY_CAP
    if _daily_count(conn, account_id, now, dm=dm) >= cap:
        raise ChatDailyCap(
            f"Daily agent {'DM' if dm else 'lobby'} cap reached.",
            retry_after_s=_seconds_until_midnight(now),
        )

    # Cooldowns: DMs use a 60s per-recipient window (dm.cooldown). Lobby posts
    # and lobby taunts share a short 10s lobby window (chat.cooldown) and must
    # never be blocked by dm.cooldown after a prior lobby message.
    last = _last_outgoing_at(
        conn, account_id, channel_id if dm else LOBBY_CHANNEL, dm=dm
    )
    if last is not None:
        elapsed = (now - last).total_seconds()
        if dm:
            if elapsed < AGENT_RECIPIENT_COOLDOWN_S:
                raise DMCooldown(
                    "Wait before messaging this recipient again.",
                    retry_after_s=max(
                        1, int(math.ceil(AGENT_RECIPIENT_COOLDOWN_S - elapsed))
                    ),
                )
        elif elapsed < AGENT_LOBBY_COOLDOWN_S:
            raise ChatCooldown(
                "Wait a moment before posting to lobby again.",
                retry_after_s=max(
                    1, int(math.ceil(AGENT_LOBBY_COOLDOWN_S - elapsed))
                ),
            )

    if dm and other_id is not None:
        if (
            _unanswered_dm_count(conn, account_id, channel_id, other_id)
            >= AGENT_UNANSWERED_DM_CAP
        ):
            raise DMUnansweredCap(
                "Wait for a reply before sending more direct messages."
            )


def _row_has(row: sqlite3.Row, key: str) -> bool:
    return key in row.keys()


def message_payload(row: sqlite3.Row) -> dict[str, object]:
    payload: dict[str, object] = {
        "contracts_version": CONTRACTS_VERSION,
        "id": row["id"],
        "channel_id": row["channel_id"],
        "account_id": row["account_id"],
        "actor_mode": row["actor_mode"],
        "body": row["body"],
        "created_at": row["created_at"],
        "deleted_at": row["deleted_at"],
    }
    kind = row["kind"] if _row_has(row, "kind") else "chat"
    match_id = row["match_id"] if _row_has(row, "match_id") else None
    if kind == "taunt" or match_id:
        payload["kind"] = kind or "chat"
        payload["match_id"] = match_id
        raw_context = (
            row["match_context_json"]
            if _row_has(row, "match_context_json")
            else None
        )
        context = None
        if raw_context:
            try:
                context = json.loads(raw_context)
            except (TypeError, ValueError):
                context = None
        payload["match_context"] = context
    return payload


def _insert_message(
    conn: sqlite3.Connection,
    channel_id: str,
    account_id: str,
    body: str,
    *,
    actor_mode: str,
    idempotency_key: str | None,
    now: datetime,
    kind: str = "chat",
    match_id: str | None = None,
    match_context_json: str | None = None,
) -> dict[str, object]:
    message_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO chats (
            id, channel_id, account_id, actor_mode, body,
            idempotency_key, created_at, deleted_at, kind, match_id,
            match_context_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
        """,
        (
            message_id,
            channel_id,
            account_id,
            actor_mode,
            body,
            idempotency_key,
            _iso(now),
            kind,
            match_id,
            match_context_json,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM chats WHERE id = ?", (message_id,)).fetchone()
    return message_payload(row)


def send_message(
    conn: sqlite3.Connection,
    channel_id: str | None,
    account_id: str,
    body: object,
    *,
    actor_mode: str = "human",
    idempotency_key: str | None = None,
    now: datetime | None = None,
    target: object | None = None,
) -> dict[str, object]:
    mode = actor_mode if actor_mode in _ACTOR_MODES else "human"

    if target is not None:
        channel = resolve_dm_channel(conn, account_id, target)
    else:
        channel = validate_channel(channel_id or "")

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
    other_id: str | None = None
    if participants is not None:
        if account_id not in participants:
            raise InvalidTarget("Only conversation participants may send here.")
        others = participants - {account_id}
        other_id = next(iter(others)) if others else None
        for other in others:
            if is_blocked_either_way(conn, account_id, other):
                raise DMBlocked("That conversation is blocked.")

    current = _now(now)
    if mode == "agent":
        _enforce_agent_limits(
            conn, account_id, channel, current, other_id=other_id
        )
    else:
        _check_rate_limit(conn, account_id, mode, current)

    return _insert_message(
        conn,
        channel,
        account_id,
        cleaned,
        actor_mode=mode,
        idempotency_key=idempotency_key,
        now=current,
    )


def _taunt_match_row(
    conn: sqlite3.Connection, match_id: str
) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT
            m.id AS match_id,
            m.status AS match_status,
            m.winner AS winner,
            m.rounds AS rounds,
            m.final_hp_json AS final_hp_json,
            m.resolved_at AS resolved_at,
            c.challenger_id AS challenger_id,
            c.defender_id AS defender_id,
            c.status AS challenge_status
        FROM matches AS m
        JOIN challenges AS c ON c.id = m.challenge_id
        WHERE m.id = ?
        """,
        (match_id,),
    ).fetchone()
    if row is None:
        raise TauntInvalidMatch("No match exists for that id.")
    return row


def _taunt_context(row: sqlite3.Row, phase: str, now: datetime) -> dict[str, object]:
    if phase == "pre":
        if row["match_status"] != "pending":
            raise TauntInvalidMatch("Pre-match taunts require a pending/queued match.")
        return {"winner": None, "final_hp": None, "rounds": None}

    if row["match_status"] != "resolved":
        raise TauntInvalidMatch("Post-match taunts require a finished match.")
    resolved_at = _parse_ts(row["resolved_at"] or "")
    if resolved_at is None or now - resolved_at > timedelta(hours=24):
        raise TauntInvalidMatch("Post-match taunts expire 24 hours after the result.")
    final_hp = None
    if row["final_hp_json"]:
        try:
            final_hp = json.loads(row["final_hp_json"])
        except (TypeError, ValueError):
            final_hp = None
    return {
        "winner": row["winner"],
        "final_hp": final_hp,
        "rounds": row["rounds"],
    }


def send_taunt(
    conn: sqlite3.Connection,
    account_id: str,
    match_id: str,
    body: object,
    *,
    phase: str,
    lobby: bool = True,
    actor_mode: str = "agent",
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    mode = actor_mode if actor_mode in _ACTOR_MODES else "human"
    current = _now(now)

    if idempotency_key:
        existing = conn.execute(
            "SELECT * FROM chats WHERE account_id = ? AND idempotency_key = ?",
            (account_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            return message_payload(existing)

    match = _taunt_match_row(conn, match_id)
    participants = {str(match["challenger_id"]), str(match["defender_id"])}
    if str(account_id) not in participants:
        raise TauntInvalidMatch("Only match participants may taunt.")

    phase_text = (phase or "").strip().lower()
    if phase_text not in _TAUNT_PHASES:
        raise TauntInvalidMatch("phase must be 'pre' or 'post'.")
    context = _taunt_context(match, phase_text, current)

    opponent = next(iter(participants - {str(account_id)}), None)
    if lobby:
        channel = LOBBY_CHANNEL
        other_id = None
    else:
        if not opponent:
            raise TauntInvalidMatch("No opponent is available for a direct taunt.")
        channel = dm_channel_for(account_id, opponent)
        other_id = opponent
        if is_blocked_either_way(conn, account_id, opponent):
            raise DMBlocked("That conversation is blocked.")

    try:
        cleaned = sanitize_display_text(body, max_chars=MAX_TAUNT_CHARS)
    except ValueError as exc:
        if str(exc) == "empty":
            raise EmptyMessage("Taunt body cannot be empty.") from exc
        raise MessageTooLong(
            f"Taunt body cannot exceed {MAX_TAUNT_CHARS} characters."
        ) from exc

    if mode == "agent":
        _enforce_agent_limits(
            conn, account_id, channel, current, other_id=other_id
        )
    else:
        _check_rate_limit(conn, account_id, mode, current)

    encoded_context = json.dumps(
        context, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return _insert_message(
        conn,
        channel,
        account_id,
        cleaned,
        actor_mode=mode,
        idempotency_key=idempotency_key,
        now=current,
        kind="taunt",
        match_id=str(match_id),
        match_context_json=encoded_context,
    )


def _cursor_parts(cursor: str | None) -> tuple[str | None, str | None]:
    if not cursor:
        return None, None
    text = str(cursor).strip()
    if not text:
        return None, None
    if "|" in text:
        stamp, _, message_id = text.partition("|")
        return stamp or None, message_id or None
    return text, None


def _cursor_timestamp(cursor: str | None) -> str | None:
    stamp, _ = _cursor_parts(cursor)
    return stamp


def _inbox_cursor(conn: sqlite3.Connection, account_id: str) -> str | None:
    row = conn.execute(
        "SELECT last_read_at FROM chat_read_cursors "
        "WHERE account_id = ? AND channel_id = ?",
        (account_id, INBOX_CURSOR_CHANNEL),
    ).fetchone()
    return row["last_read_at"] if row is not None else None


def inbox(
    conn: sqlite3.Connection,
    account_id: str,
    *,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[dict[str, object]], str | None]:
    """Return unread DMs and lobby @mentions, oldest first."""

    account = conn.execute(
        "SELECT id, public_handle FROM accounts WHERE id = ? AND status = 'active'",
        (account_id,),
    ).fetchone()
    if account is None:
        raise InvalidTarget("No active account exists for that inbox.")

    effective_cursor = cursor
    if effective_cursor is None:
        effective_cursor = _inbox_cursor(conn, account_id)
    stamp, message_id = _cursor_parts(effective_cursor)

    clauses = [
        "deleted_at IS NULL",
        "account_id <> ?",
        "(channel_id LIKE 'dm:%' OR channel_id LIKE 'direct:%' OR channel_id = 'lobby')",
    ]
    params: list[object] = [account_id]
    if stamp:
        if message_id:
            clauses.append("(created_at > ? OR (created_at = ? AND id > ?))")
            params.extend([stamp, stamp, message_id])
        else:
            clauses.append("created_at > ?")
            params.append(stamp)
    params.append(10000)

    rows = conn.execute(
        f"""
        SELECT * FROM chats
        WHERE {' AND '.join(clauses)}
        ORDER BY created_at ASC, id ASC
        LIMIT ?
        """,
        params,
    ).fetchall()

    handle = str(account["public_handle"] or "")
    mention_re = None
    if handle:
        mention_re = re.compile(
            r"(?<![A-Za-z0-9_])@" + re.escape(handle) + r"(?![A-Za-z0-9_])",
            re.IGNORECASE,
        )
    blocked = blocked_account_ids(conn, account_id)

    selected: list[sqlite3.Row] = []
    for row in rows:
        if str(row["account_id"]) in blocked:
            continue
        participants = _direct_participants(str(row["channel_id"]))
        if participants is not None:
            if account_id in participants:
                selected.append(row)
            continue
        if row["channel_id"] == LOBBY_CHANNEL and mention_re is not None:
            if mention_re.search(str(row["body"])):
                selected.append(row)

    capped = max(1, min(int(limit), 100))
    page = selected[:capped]
    messages = [message_payload(row) for row in page]
    next_cursor = (
        f"{page[-1]['created_at']}|{page[-1]['id']}" if page else effective_cursor
    )
    return messages, next_cursor


def mark_inbox_read(
    conn: sqlite3.Connection,
    account_id: str,
    cursor: str | None = None,
    *,
    channel_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    channel = validate_channel(channel_id or INBOX_CURSOR_CHANNEL)
    stamp = _cursor_timestamp(cursor) or _iso(_now(now))
    conn.execute(
        """
        INSERT INTO chat_read_cursors (account_id, channel_id, last_read_at)
        VALUES (?, ?, ?)
        ON CONFLICT(account_id, channel_id) DO UPDATE SET
            last_read_at = excluded.last_read_at
        """,
        (account_id, channel, stamp),
    )
    conn.commit()
    return {
        "account_id": account_id,
        "channel_id": channel,
        "last_read_at": stamp,
    }


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
