"""Account identity, owner policy and live agent-chat settings projection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlite3 import Connection

from .. import CONTRACTS_VERSION
from ..db import account_exists, get_current_account_id, get_db
from ..social import get_chat_settings, set_agent_chat_enabled

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


class ChatSettingsUpdate(BaseModel):
    agent_chat_enabled: bool | None = None
    chat_enabled: bool | None = None
    model_config = ConfigDict(extra="ignore")

    def resolved_enabled(self) -> bool | None:
        if self.agent_chat_enabled is not None:
            return self.agent_chat_enabled
        return self.chat_enabled


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "unauthorized", "message": "A valid account session is required."},
    )


def _me_payload(conn: Connection, account_id: str) -> dict[str, object]:
    row = conn.execute(
        "SELECT id, public_handle, status, created_at FROM accounts WHERE id = ?",
        (account_id,),
    ).fetchone()

    pet_row = conn.execute(
        "SELECT id FROM pets WHERE account_id = ? ORDER BY created_at LIMIT 1",
        (account_id,),
    ).fetchone()

    chat_settings = get_chat_settings(conn, account_id)
    chat_enabled = bool(chat_settings["agent_chat_enabled"])
    policy = dict(DEFAULT_POLICY)
    policy["chat_enabled"] = chat_enabled

    return {
        "contracts_version": CONTRACTS_VERSION,
        "pet_id": pet_row["id"] if pet_row else None,
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
            "chat": chat_enabled,
            "purchases": False,
        },
        "policy": policy,
        "chat_settings": chat_settings,
    }


@router.get("/me")
def get_me(
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, object]:
    if not account_exists(conn, account_id):
        raise _unauthorized()
    return _me_payload(conn, account_id)


def _update_chat_settings(
    payload: ChatSettingsUpdate,
    account_id: str,
    conn: Connection,
) -> dict[str, object]:
    if not account_exists(conn, account_id):
        raise _unauthorized()
    enabled = payload.resolved_enabled()
    if enabled is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": "agent_chat_enabled or chat_enabled is required.",
            },
        )
    set_agent_chat_enabled(conn, account_id, enabled)
    return _me_payload(conn, account_id)


@router.patch("/me/policy")
@router.put("/me/policy")
@router.patch("/me/chat-settings")
@router.put("/me/chat-settings")
def update_chat_settings(
    payload: ChatSettingsUpdate,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, object]:
    return _update_chat_settings(payload, account_id, conn)
