"""Once-only reward entitlements for completed matches."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from ..db import utc_now_iso
from .ledger import credit, ledger_payload, wallet_allowances, write_transaction


def income_allowances(
    conn: sqlite3.Connection, account_id: str, at: str | None = None
) -> dict[str, int]:
    """Remaining practice/PvP income allowances for the wallet projection."""
    return wallet_allowances(conn, account_id, at)


def _entitlement_source(match_id: str, account_id: str, kind: str) -> str:
    return f"entitlement:{match_id}:{account_id}:{kind}"


def _receipt_for(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    if row["ledger_id"]:
        ledger_row = conn.execute(
            "SELECT * FROM ledger WHERE id = ?", (row["ledger_id"],)
        ).fetchone()
        if ledger_row is not None:
            return ledger_payload(ledger_row)
    ledger_row = conn.execute(
        "SELECT * FROM ledger WHERE source_event_id = ?",
        (_entitlement_source(row["match_id"], row["account_id"], row["kind"]),),
    ).fetchone()
    return ledger_payload(ledger_row)


def grant_entitlement(
    conn: sqlite3.Connection,
    match_id: str,
    account_id: str,
    kind: str,
    bits: int,
    xp: int = 0,
) -> dict[str, Any]:
    """Grant a match reward exactly once per ``(match_id, account_id, kind)``.

    Bits and XP land in the same transaction as the entitlement row.  A retry
    returns the original ledger receipt and does not move the wallet or pet.
    """
    bits = int(bits)
    xp = int(xp)
    if bits < 0 or xp < 0:
        raise ValueError("bits and xp must not be negative")

    with write_transaction(conn):
        existing = conn.execute(
            """
            SELECT * FROM reward_entitlements
            WHERE match_id = ? AND account_id = ? AND kind = ?
            """,
            (match_id, account_id, kind),
        ).fetchone()
        if existing is not None:
            return _receipt_for(conn, existing)

        receipt = credit(
            conn,
            account_id,
            bits,
            f"reward.{kind}"[:64],
            _entitlement_source(match_id, account_id, kind),
        )
        conn.execute(
            """
            INSERT INTO reward_entitlements (
                id, match_id, account_id, kind, bits, xp, ledger_id, awarded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                match_id,
                account_id,
                kind,
                bits,
                xp,
                receipt["id"],
                utc_now_iso(),
            ),
        )
        if xp:
            conn.execute(
                "UPDATE pets SET xp = xp + ? WHERE account_id = ?",
                (xp, account_id),
            )
        return receipt
