"""Abuse report persistence.

Report reasons are moderator-facing untrusted text. They are stored verbatim
after control-character removal and are never interpreted as instructions.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from .errors import InvalidTarget
from .sanitize import MAX_REASON_CHARS, sanitize_display_text

TARGET_TYPES = frozenset({"message", "account", "pet", "channel"})
STATUS_OPEN = "open"

_PAYLOAD_FIELDS = (
    "id",
    "reporter_id",
    "target_type",
    "target_id",
    "reason",
    "status",
    "created_at",
)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def report_payload(row: sqlite3.Row) -> dict[str, object]:
    return {field: row[field] for field in _PAYLOAD_FIELDS}


def create_report(
    conn: sqlite3.Connection,
    reporter_id: str,
    target_type: str,
    target_id: str,
    reason: object,
    *,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    kind = (target_type or "").strip().lower()
    if kind not in TARGET_TYPES:
        raise InvalidTarget("target_type must be message, account, pet or channel.")

    try:
        target = sanitize_display_text(target_id, max_chars=128)
    except ValueError as exc:
        raise InvalidTarget("A valid target_id is required.") from exc

    try:
        cleaned_reason = sanitize_display_text(reason, max_chars=MAX_REASON_CHARS)
    except ValueError as exc:
        raise InvalidTarget(
            f"A reason of 1-{MAX_REASON_CHARS} characters is required."
        ) from exc

    if idempotency_key:
        existing = conn.execute(
            "SELECT * FROM moderation_reports "
            "WHERE reporter_id = ? AND idempotency_key = ?",
            (reporter_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            return report_payload(existing)

    report_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO moderation_reports (
            id, reporter_id, target_type, target_id, reason, status,
            idempotency_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report_id,
            reporter_id,
            kind,
            target,
            cleaned_reason,
            STATUS_OPEN,
            idempotency_key,
            _iso(_now(now)),
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM moderation_reports WHERE id = ?", (report_id,)
    ).fetchone()
    return report_payload(row)
