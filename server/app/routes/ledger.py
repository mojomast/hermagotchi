"""Paginated, account-scoped ledger history (contracts-v1 LedgerEntry)."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import CONTRACTS_VERSION
from ..db import account_exists, get_current_account_id, get_db
from ..economy import ensure_wallet
from ..economy.ledger import ledger_payload

router = APIRouter(tags=["economy"])


@router.get("/ledger")
def get_ledger(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
    per_page: int | None = Query(default=None, ge=1, le=100),
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    if page_size is not None:
        limit = page_size
    elif per_page is not None:
        limit = per_page
    if page is not None:
        offset = (page - 1) * limit
    if not account_exists(conn, account_id):
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "A valid account session is required."},
        )
    ensure_wallet(conn, account_id)

    total = conn.execute(
        "SELECT COUNT(*) AS n FROM ledger WHERE account_id = ?", (account_id,)
    ).fetchone()["n"]
    rows = conn.execute(
        """
        SELECT * FROM ledger
        WHERE account_id = ?
        ORDER BY created_at DESC, rowid DESC
        LIMIT ? OFFSET ?
        """,
        (account_id, limit, offset),
    ).fetchall()
    next_offset = offset + len(rows)
    entries = [ledger_payload(row) for row in rows]
    return {
        "contracts_version": CONTRACTS_VERSION,
        "account_id": account_id,
        "entries": entries,
        "items": entries,
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": next_offset if next_offset < total else None,
    }
