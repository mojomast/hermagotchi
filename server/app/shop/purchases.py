"""Atomic, idempotent item purchases on top of the economy ledger."""

from __future__ import annotations

import hashlib
import sqlite3
from typing import Any

from .. import CONTRACTS_VERSION
from ..db import utc_now_iso
from ..economy import debit, wallet_payload
from .catalog import get_item, item_payload
from .errors import (
    IdempotencyConflict,
    InvalidIdempotencyKey,
    ItemAlreadyOwned,
    ItemInactive,
    ItemNotFound,
)
from .transactions import write_transaction

MAX_IDEMPOTENCY_LEN = 128


def normalise_key(idempotency_key: str | None) -> str:
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise InvalidIdempotencyKey("A non-empty idempotency_key is required.")
    key = idempotency_key.strip()
    if len(key) > MAX_IDEMPOTENCY_LEN:
        raise InvalidIdempotencyKey(
            f"idempotency_key must be at most {MAX_IDEMPOTENCY_LEN} characters."
        )
    return key


def purchase_source_event(account_id: str, idempotency_key: str) -> str:
    digest = hashlib.sha256(
        f"{account_id}:{idempotency_key}".encode("utf-8")
    ).hexdigest()[:48]
    return f"shop.buy:{digest}"


def _payload(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    receipt: dict[str, Any],
    *,
    duplicate: bool,
    acquired_at: str,
) -> dict[str, Any]:
    return {
        "contracts_version": CONTRACTS_VERSION,
        "item": item_payload(row),
        "duplicate": duplicate,
        "acquired_at": acquired_at,
        "receipt": receipt,
        "wallet": wallet_payload(conn, receipt["account_id"]),
    }


def _replay(
    conn: sqlite3.Connection, account_id: str, item_id: str, source_event_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM ledger WHERE source_event_id = ?", (source_event_id,)
    ).fetchone()
    if row is None:
        return None
    if row["account_id"] != account_id:
        raise IdempotencyConflict("That idempotency key belongs to another account.")
    owned = conn.execute(
        "SELECT * FROM inventory WHERE source_event_id = ?", (source_event_id,)
    ).fetchone()
    if owned is None or owned["item_id"] != item_id:
        raise IdempotencyConflict(
            "That idempotency key was already used for a different item."
        )
    item_row = get_item(conn, item_id)
    if item_row is None:
        raise ItemNotFound("No item exists for that id.")
    receipt = debit(
        conn,
        account_id,
        item_row["price_bits"],
        "shop.purchase",
        source_event_id,
    )
    return _payload(
        conn,
        item_row,
        receipt,
        duplicate=True,
        acquired_at=owned["acquired_at"],
    )


def purchase_item(
    conn: sqlite3.Connection,
    account_id: str,
    item_id: str,
    idempotency_key: str | None,
) -> dict[str, Any]:
    key = normalise_key(idempotency_key)
    source_event_id = purchase_source_event(account_id, key)

    with write_transaction(conn):
        replay = _replay(conn, account_id, item_id, source_event_id)
        if replay is not None:
            return replay

        item_row = get_item(conn, item_id)
        if item_row is None:
            raise ItemNotFound("No item exists for that id.")
        if not bool(item_row["active"]):
            raise ItemInactive("That item is not currently for sale.")

        owned = conn.execute(
            "SELECT 1 FROM inventory WHERE account_id = ? AND item_id = ?",
            (account_id, item_id),
        ).fetchone()
        if owned is not None:
            raise ItemAlreadyOwned("This account already owns that item.")

        receipt = debit(
            conn,
            account_id,
            item_row["price_bits"],
            "shop.purchase",
            source_event_id,
        )

        acquired_at = utc_now_iso()
        conn.execute(
            """
            INSERT INTO inventory (account_id, item_id, acquired_at, source_event_id)
            VALUES (?, ?, ?, ?)
            """,
            (account_id, item_id, acquired_at, source_event_id),
        )
        return _payload(
            conn, item_row, receipt, duplicate=False, acquired_at=acquired_at
        )
