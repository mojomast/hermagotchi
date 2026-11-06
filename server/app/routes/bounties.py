"""Active daily bounties and one-time claim endpoints."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .. import CONTRACTS_VERSION
from ..db import account_exists, get_current_account_id, get_db
from ..economy import EconomyError, claim_bounty, list_bounties

router = APIRouter(tags=["economy"])


def _require_account(conn: Connection, account_id: str) -> None:
    if not account_exists(conn, account_id):
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "A valid account session is required."},
        )


@router.get("/bounties")
def get_bounties(
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    return {
        "contracts_version": CONTRACTS_VERSION,
        "bounties": list_bounties(conn, account_id),
    }


@router.post("/bounties/{bounty_id}/claim")
def post_claim_bounty(
    bounty_id: str,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        result = claim_bounty(conn, bounty_id, account_id)
    except EconomyError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return {"contracts_version": CONTRACTS_VERSION, **result}
