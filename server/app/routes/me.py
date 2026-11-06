"""Account identity and owner policy projection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlite3 import Connection

from .. import CONTRACTS_VERSION
from ..db import account_exists, get_current_account_id, get_db

router = APIRouter(tags=["identity"])

DEFAULT_POLICY: dict[str, object] = {
    "contracts_version": CONTRACTS_VERSION,
    "mode": "human",
    "network_enabled": False,
    "autonomy_enabled": False,
    "chat_enabled": False,
    "autonomous_battles_per_day": 3,
    "agent_chat_messages_per_day": 2,
    "llm_decisions_per_day": 4,
}


@router.get("/me")
def get_me(
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, object]:
    if not account_exists(conn, account_id):
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "A valid account session is required."},
        )

    row = conn.execute(
        "SELECT id, public_handle, status, created_at FROM accounts WHERE id = ?",
        (account_id,),
    ).fetchone()

    return {
        "contracts_version": CONTRACTS_VERSION,
        "account": {
            "id": row["id"],
            "public_handle": row["public_handle"],
            "status": row["status"],
            "created_at": row["created_at"],
        },
        "permissions": {
            "adopt": True,
            "care": False,
            "network": False,
            "autonomy": False,
            "chat": False,
            "purchases": False,
        },
        "policy": dict(DEFAULT_POLICY),
    }
