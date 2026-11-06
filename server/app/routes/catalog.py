"""Versioned shop catalog route (contracts-v1 Item)."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..db import account_exists, get_current_account_id, get_db
from ..shop import list_catalog

router = APIRouter(tags=["shop"])


def _require_account(conn: Connection, account_id: str) -> None:
    if not account_exists(conn, account_id):
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "A valid account session is required."},
        )


@router.get("/catalog")
def get_catalog(
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    return list_catalog(conn)
