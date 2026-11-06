"""Owner-authorised goal persistence (contracts-v1, HGT-W5-L).

This is an optional server-side mirror of the plugin's local goal loop. It only
stores allowlisted target ids and budgets; it never reads art assets or accepts
free-form chat text as a goal.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from sqlite3 import Connection
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .. import CONTRACTS_VERSION
from ..db import account_exists, get_current_account_id, get_db, utc_now_iso

router = APIRouter(tags=["goals"])

GoalType = Literal["cosmetic", "rank", "achievement"]
ChosenBy = Literal["human", "agent", "co-op", "coop"]
Status = Literal["active", "cleared", "expired"]


class GoalRequest(BaseModel):
    type: GoalType | None = None
    target_type: GoalType | None = None
    target_id: str = Field(min_length=1, max_length=64)
    chosen_by: ChosenBy = "human"
    spending_limit_bits: int = Field(default=0, ge=0)
    max_battles: int = Field(default=0, ge=0)
    expires_at: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _flatten_goal(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("goal"), dict):
            merged = dict(data["goal"])
            merged.update(
                {key: value for key, value in data.items() if key != "goal"}
            )
            return merged
        return data

    def resolved_type(self) -> GoalType:
        value = self.type or self.target_type
        if value not in ("cosmetic", "rank", "achievement"):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "goal_type_invalid",
                    "message": "type must be cosmetic, rank, or achievement.",
                },
            )
        return value


def _require_account(conn: Connection, account_id: str) -> None:
    if not account_exists(conn, account_id):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "unauthorized",
                "message": "A valid account session is required.",
            },
        )


def _valid_target(target_id: str) -> bool:
    value = target_id.strip()
    if not value or len(value) > 64:
        return False
    if "://" in value or "/" in value or "\\" in value or any(ch.isspace() for ch in value):
        return False
    return all(ch.isalnum() or ch in "._:-" for ch in value)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "type": row["type"],
        "target_id": row["target_id"],
        "chosen_by": row["chosen_by"],
        "chosen_at": row["chosen_at"],
        "spending_limit_bits": row["spending_limit_bits"],
        "max_battles": row["max_battles"],
        "expires_at": row["expires_at"],
        "status": row["status"],
        "revision": row["revision"],
    }


def _active(conn: Connection, account_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM goals
        WHERE account_id = ? AND status = 'active'
        ORDER BY chosen_at DESC, revision DESC
        LIMIT 1
        """,
        (account_id,),
    ).fetchone()


@router.get("/goals")
def get_goals(
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    active = _row(_active(conn, account_id))
    return {
        "contracts_version": CONTRACTS_VERSION,
        "goal": active,
        "goals": [active] if active is not None else [],
    }


@router.post("/goals", status_code=201)
def set_goal(
    payload: GoalRequest,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    goal_type = payload.resolved_type()
    target_id = payload.target_id.strip()
    if not _valid_target(target_id):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "goal_target_invalid",
                "message": "target_id must be an allowlisted catalog or rank id.",
            },
        )
    chosen_by = "co-op" if payload.chosen_by == "coop" else payload.chosen_by
    expires = _parse_iso(payload.expires_at)
    if payload.expires_at is not None and expires is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "goal_expiry_invalid", "message": "expires_at must be ISO-8601."},
        )

    key = (payload.idempotency_key or idempotency_header or "").strip() or None
    if key is not None:
        existing = conn.execute(
            """
            SELECT * FROM goals
            WHERE account_id = ? AND idempotency_key = ?
            LIMIT 1
            """,
            (account_id, key),
        ).fetchone()
        if existing is not None:
            return {"contracts_version": CONTRACTS_VERSION, "goal": _row(existing)}

    now = utc_now_iso()
    goal_id = str(uuid.uuid4())
    with conn:
        conn.execute(
            """
            UPDATE goals
            SET status = 'cleared', revision = revision + 1
            WHERE account_id = ? AND status = 'active'
            """,
            (account_id,),
        )
        conn.execute(
            """
            INSERT INTO goals (
                id, account_id, type, target_id, chosen_by, chosen_at,
                spending_limit_bits, max_battles, expires_at, status,
                revision, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 1, ?)
            """,
            (
                goal_id,
                account_id,
                goal_type,
                target_id,
                chosen_by,
                now,
                int(payload.spending_limit_bits),
                int(payload.max_battles),
                payload.expires_at,
                key,
            ),
        )
    row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    return {"contracts_version": CONTRACTS_VERSION, "goal": _row(row)}


def _clear(conn: Connection, account_id: str) -> dict[str, Any]:
    row = _active(conn, account_id)
    with conn:
        changed = conn.execute(
            """
            UPDATE goals
            SET status = 'cleared', revision = revision + 1
            WHERE account_id = ? AND status = 'active'
            """,
            (account_id,),
        ).rowcount
    return {
        "contracts_version": CONTRACTS_VERSION,
        "goal": None,
        "cleared": bool(changed),
        "previous": _row(row),
    }


@router.delete("/goals")
def clear_goal(
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    return _clear(conn, account_id)


@router.post("/goals/clear")
def clear_goal_alias(
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    return _clear(conn, account_id)
