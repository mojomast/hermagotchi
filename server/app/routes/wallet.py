"""Authenticated wallet projection (contracts-v1 Wallet).

``ensure_wallet`` augments the balance with live practice/PvP allowance
counters derived from the ledger.
"""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..db import account_exists, get_current_account_id, get_db
from ..economy import ensure_wallet

router = APIRouter(tags=["economy"])


def _require_account(conn: Connection, account_id: str) -> None:
    if not account_exists(conn, account_id):
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "A valid account session is required."},
        )


@router.get("/wallet")
def get_wallet(
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    return ensure_wallet(conn, account_id)
