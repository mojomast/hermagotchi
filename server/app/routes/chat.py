"""Moderated chat, block list and abuse report endpoints."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .. import CONTRACTS_VERSION
from ..db import account_exists, get_current_account_id, get_db
from ..social import (
    SocialError,
    block_account,
    create_report,
    list_blocks,
    list_messages,
    send_message,
    unblock_account,
)
from ..social.sanitize import MAX_MESSAGE_CHARS, MAX_REASON_CHARS

router = APIRouter(tags=["social"])

_Unauthorized = HTTPException(
    status_code=401,
    detail={"code": "unauthorized", "message": "A valid account session is required."},
)


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    actor_mode: Literal["human", "agent"] = "human"
    idempotency_key: str | None = Field(default=None, max_length=128)
    model_config = ConfigDict(extra="ignore")


class BlockCreate(BaseModel):
    blocked_id: str = Field(min_length=1, max_length=64)
    idempotency_key: str | None = Field(default=None, max_length=128)
    model_config = ConfigDict(extra="ignore")


class ReportCreate(BaseModel):
    target_type: Literal["message", "account", "pet", "channel"]
    target_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=MAX_REASON_CHARS)
    idempotency_key: str | None = Field(default=None, max_length=128)
    model_config = ConfigDict(extra="ignore")


def _require_account(conn: Connection, account_id: str) -> None:
    if not account_exists(conn, account_id):
        raise _Unauthorized


def _raise_social(exc: SocialError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.to_detail())


@router.get("/chat/channels/{channel_id}/messages")
def get_messages(
    channel_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    before: str | None = Query(default=None, max_length=64),
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        messages, next_before = list_messages(
            conn,
            channel_id,
            viewer_id=account_id,
            limit=limit,
            before=before,
        )
    except SocialError as exc:
        _raise_social(exc)
    return {
        "contracts_version": CONTRACTS_VERSION,
        "channel_id": channel_id,
        "messages": messages,
        "next_before": next_before,
    }


@router.post("/chat/channels/{channel_id}/messages", status_code=201)
def post_message(
    channel_id: str,
    payload: MessageCreate,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        message = send_message(
            conn,
            channel_id,
            account_id,
            payload.body,
            actor_mode=payload.actor_mode,
            idempotency_key=payload.idempotency_key,
        )
    except SocialError as exc:
        _raise_social(exc)
    return {"contracts_version": CONTRACTS_VERSION, "message": message}


@router.post("/moderation/report", status_code=201)
def post_report(
    payload: ReportCreate,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        report = create_report(
            conn,
            account_id,
            payload.target_type,
            payload.target_id,
            payload.reason,
            idempotency_key=payload.idempotency_key,
        )
    except SocialError as exc:
        _raise_social(exc)
    return {"contracts_version": CONTRACTS_VERSION, "report": report}


@router.get("/blocks")
def get_blocks(
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    return {
        "contracts_version": CONTRACTS_VERSION,
        "blocks": list_blocks(conn, account_id),
    }


@router.post("/blocks", status_code=201)
def post_block(
    payload: BlockCreate,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        block = block_account(conn, account_id, payload.blocked_id)
    except SocialError as exc:
        _raise_social(exc)
    return {"contracts_version": CONTRACTS_VERSION, "block": block}


@router.delete("/blocks/{blocked_id}")
def delete_block(
    blocked_id: str,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    removed = unblock_account(conn, account_id, blocked_id)
    return {
        "contracts_version": CONTRACTS_VERSION,
        "blocked_id": blocked_id,
        "removed": removed,
    }
