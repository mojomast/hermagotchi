"""Match status, replay and tactics submission routes."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..db import get_current_account_id, get_db
from ..matchmaking import MatchmakingError, get_match, submit_tactics

router = APIRouter(tags=["matches"])

_CARD_FIELDS = ("ruleset_version", "stance", "actions", "emote_id")


class TacticsSubmit(BaseModel):
    card: dict[str, Any] | None = None
    tactics: dict[str, Any] | None = None
    tactic: dict[str, Any] | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)
    model_config = ConfigDict(extra="allow")

    def resolved_card(self) -> dict[str, Any] | None:
        for value in (self.card, self.tactics, self.tactic):
            if isinstance(value, dict):
                return value
        raw = self.model_dump()
        direct = {key: raw[key] for key in _CARD_FIELDS if key in raw}
        return direct or None


def _raise(exc: MatchmakingError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.to_detail())


@router.post("/matches/{match_id}/tactics")
def lock_tactics(
    match_id: str,
    payload: TacticsSubmit,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    try:
        match, replay = submit_tactics(
            conn, match_id, account_id, payload.resolved_card()
        )
    except MatchmakingError as exc:
        _raise(exc)
    return {"match": match, "replay": replay}


@router.get("/matches/{match_id}")
def read_match(
    match_id: str,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    try:
        match, replay = get_match(conn, match_id, account_id)
    except MatchmakingError as exc:
        _raise(exc)
    return {"match": match, "replay": replay}
