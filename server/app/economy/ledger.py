"""Authoritative wallet projection and append-only ledger primitives.

Every balance-changing operation runs in one write transaction (``BEGIN
IMMEDIATE`` on SQLite) so that the wallet row and the ledger row are committed
together.  ``source_event_id`` is unique, making retries idempotent: a repeated
event returns the original ledger receipt and never credits twice.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any

from .. import CONTRACTS_VERSION
from ..db import utc_now_iso
from .errors import (
    InsufficientFunds,
    InvalidAmount,
    InvalidSourceEvent,
    SourceEventConflict,
)

MAX_REASON_LEN = 64
MAX_SOURCE_EVENT_LEN = 128


@contextmanager
def write_transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Own a write transaction, or join one the caller already started."""
    started_here = not conn.in_transaction
    if started_here:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        if started_here:
            conn.rollback()
        raise
    else:
        if started_here:
            conn.commit()


def _wallet_row(conn: sqlite3.Connection, account_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT account_id, balance, revision FROM wallets WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT OR IGNORE INTO wallets (account_id, balance, revision) VALUES (?, 0, 0)",
            (account_id,),
        )
        row = conn.execute(
            "SELECT account_id, balance, revision FROM wallets WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    return row


def wallet_payload(conn: sqlite3.Connection, account_id: str) -> dict[str, Any]:
    row = _wallet_row(conn, account_id)
    return {
        "contracts_version": CONTRACTS_VERSION,
        "account_id": row["account_id"],
        "currency": "bits",
        "balance": row["balance"],
        "revision": row["revision"],
    }


def ensure_wallet(conn: sqlite3.Connection, account_id: str) -> dict[str, Any]:
    """Return the account wallet, creating a zero-balance row if needed."""
    with write_transaction(conn):
        payload = wallet_payload(conn, account_id)
    return payload


def ledger_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "contracts_version": CONTRACTS_VERSION,
        "id": row["id"],
        "account_id": row["account_id"],
        "delta": row["delta"],
        "reason": row["reason"],
        "source_event_id": row["source_event_id"],
        "balance_after": row["balance_after"],
        "created_at": row["created_at"],
    }


def _existing_receipt(
    conn: sqlite3.Connection, account_id: str, source_event_id: str
) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT * FROM ledger WHERE source_event_id = ?", (source_event_id,)
    ).fetchone()
    if row is not None and row["account_id"] != account_id:
        raise SourceEventConflict(
            "That source event already belongs to a different account."
        )
    return row


def _normalise(
    amount: int | None, delta: int | None, *, allow_negative: bool = False
) -> int:
    if amount is None:
        amount = delta
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise InvalidAmount("Amount must be an integer number of Bits.")
    if amount < 0 and not allow_negative:
        raise InvalidAmount("Amount must not be negative.")
    return amount


def _validate_text(value: str | None, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidSourceEvent(f"{field} must be a non-empty string.")
    value = value.strip()
    if len(value) > limit:
        raise InvalidSourceEvent(f"{field} must be at most {limit} characters.")
    return value


def _apply(
    conn: sqlite3.Connection,
    account_id: str,
    amount: int,
    *,
    negative: bool,
    reason: str,
    source_event_id: str,
) -> dict[str, Any]:
    reason = _validate_text(reason, "reason", MAX_REASON_LEN)
    source_event_id = _validate_text(
        source_event_id, "source_event_id", MAX_SOURCE_EVENT_LEN
    )
    amount = abs(amount) if negative else amount
    signed_delta = -amount if negative else amount

    with write_transaction(conn):
        existing = _existing_receipt(conn, account_id, source_event_id)
        if existing is not None:
            return ledger_payload(existing)

        wallet = _wallet_row(conn, account_id)
        balance_after = wallet["balance"] + signed_delta
        if balance_after < 0:
            raise InsufficientFunds("Not enough Bits for this debit.")

        ledger_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        conn.execute(
            """
            INSERT INTO ledger (
                id, account_id, delta, reason, source_event_id,
                balance_after, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ledger_id,
                account_id,
                signed_delta,
                reason,
                source_event_id,
                balance_after,
                created_at,
            ),
        )
        conn.execute(
            "UPDATE wallets SET balance = ?, revision = revision + 1 WHERE account_id = ?",
            (balance_after, account_id),
        )
        row = conn.execute("SELECT * FROM ledger WHERE id = ?", (ledger_id,)).fetchone()
        return ledger_payload(row)


def credit(
    conn: sqlite3.Connection,
    account_id: str,
    amount: int | None = None,
    reason: str | None = None,
    source_event_id: str | None = None,
    *,
    delta: int | None = None,
) -> dict[str, Any]:
    """Credit Bits once per ``source_event_id`` and return the ledger receipt."""
    resolved = _normalise(amount, delta)
    return _apply(
        conn,
        account_id,
        resolved,
        negative=False,
        reason=reason or "",
        source_event_id=source_event_id or "",
    )


def debit(
    conn: sqlite3.Connection,
    account_id: str,
    amount: int | None = None,
    reason: str | None = None,
    source_event_id: str | None = None,
    *,
    delta: int | None = None,
) -> dict[str, Any]:
    """Debit Bits atomically, refusing to create a negative balance."""
    resolved = _normalise(amount, delta, allow_negative=True)
    return _apply(
        conn,
        account_id,
        resolved,
        negative=True,
        reason=reason or "",
        source_event_id=source_event_id or "",
    )


def ledger_sum(conn: sqlite3.Connection, account_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(delta), 0) AS total FROM ledger WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    return int(row["total"])


def wallet_reconciles(conn: sqlite3.Connection, account_id: str) -> bool:
    wallet = _wallet_row(conn, account_id)
    return wallet["balance"] == ledger_sum(conn, account_id)
