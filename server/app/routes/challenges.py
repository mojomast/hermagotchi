"""Authenticated async challenge creation and response routes."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..db import get_current_account_id, get_db
from ..matchmaking import (
    MatchmakingError,
    create_challenge,
    respond_to_challenge,
)

router = APIRouter(tags=["challenges"])


class ChallengeCreate(BaseModel):
    defender_id: str | None = None
    opponent_id: str | None = None
    mode: Literal["practice", "casual", "ranked"] = "casual"
    expires_in_s: int | None = Field(default=None, ge=60, le=30 * 24 * 60 * 60)
    idempotency_key: str | None = Field(default=None, max_length=128)
    model_config = ConfigDict(extra="ignore")


class ChallengeResponse(BaseModel):
    action: str | None = None
    decision: str | None = None
    response: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)
    model_config = ConfigDict(extra="ignore")

    def resolved_action(self) -> str | None:
        value = self.action or self.decision or self.response
        return value.strip().lower() if isinstance(value, str) else value


def _raise(exc: MatchmakingError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.to_detail())


@router.post("/challenges", status_code=201)
def invite(
    payload: ChallengeCreate,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return create_challenge(
            conn,
            challenger_id=account_id,
            defender_id=payload.defender_id or payload.opponent_id,
            mode=payload.mode,
            expires_in_s=payload.expires_in_s,
            idempotency_key=payload.idempotency_key or idempotency_header,
        )
    except MatchmakingError as exc:
        _raise(exc)


@router.post("/challenges/{challenge_id}/respond")
def respond(
    challenge_id: str,
    payload: ChallengeResponse,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    action = payload.resolved_action()
    if action not in ("accept", "decline"):
        raise HTTPException(
            status_code=422,
            detail={"code": "action_invalid", "message": "action must be accept or decline."},
        )
    try:
        challenge, match = respond_to_challenge(conn, challenge_id, account_id, action)
    except MatchmakingError as exc:
        _raise(exc)
    return {"challenge": challenge, "match": match}
