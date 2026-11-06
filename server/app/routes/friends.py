"""Friend requests, presence and social-history endpoints (HGT-W14-A)."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .. import CONTRACTS_VERSION
from ..db import account_exists, get_current_account_id, get_db
from ..social import (
    InvalidTarget,
    SocialError,
    list_friend_requests,
    list_friends,
    list_social_history,
    remove_friend,
    resolve_target_account,
    respond_friend_request,
    send_friend_request,
    touch_presence,
)

router = APIRouter(tags=["social"])

_Unauthorized = HTTPException(
    status_code=401,
    detail={"code": "unauthorized", "message": "A valid account session is required."},
)


class FriendRequestCreate(BaseModel):
    account_id: str | None = Field(default=None, max_length=64)
    friend_id: str | None = Field(default=None, max_length=64)
    to_account_id: str | None = Field(default=None, max_length=64)
    target: str | None = Field(default=None, max_length=128)
    model_config = ConfigDict(extra="ignore")


class FriendRespond(BaseModel):
    action: str | None = Field(default=None, min_length=1, max_length=16)
    status: str | None = Field(default=None, min_length=1, max_length=16)
    model_config = ConfigDict(extra="ignore")


def _require_account(conn: Connection, account_id: str) -> None:
    if not account_exists(conn, account_id):
        raise _Unauthorized


def _raise_social(exc: SocialError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.to_detail())


@router.get("/friends")
def get_friends(
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        touch_presence(conn, account_id)
        friends = list_friends(conn, account_id)
        requests = list_friend_requests(conn, account_id)
    except SocialError as exc:
        _raise_social(exc)
    return {
        "contracts_version": CONTRACTS_VERSION,
        "friends": friends,
        "incoming_requests": requests["incoming"],
        "outgoing_requests": requests["outgoing"],
    }


@router.post("/friends", status_code=201)
def post_friend_request(
    payload: FriendRequestCreate,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        target = (
            payload.account_id
            or payload.friend_id
            or payload.to_account_id
            or payload.target
        )
        if not target:
            raise InvalidTarget("A friend account id or target is required.")
        resolved = resolve_target_account(conn, target)
        request = send_friend_request(conn, account_id, resolved)
    except SocialError as exc:
        _raise_social(exc)
    return {"contracts_version": CONTRACTS_VERSION, "request": request}


@router.post("/friends/requests/{request_id}/respond")
def post_friend_response(
    request_id: str,
    payload: FriendRespond,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        action = payload.action or payload.status
        if not action:
            raise InvalidTarget("action must be 'accept' or 'decline'.")
        request = respond_friend_request(conn, account_id, request_id, action)
    except SocialError as exc:
        _raise_social(exc)
    return {"contracts_version": CONTRACTS_VERSION, "request": request}


@router.delete("/friends/{friend_id}")
def delete_friend(
    friend_id: str,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        result = remove_friend(conn, account_id, friend_id)
    except SocialError as exc:
        _raise_social(exc)
    return {"contracts_version": CONTRACTS_VERSION, **result}


@router.post("/presence")
def post_presence(
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        presence = touch_presence(conn, account_id)
    except SocialError as exc:
        _raise_social(exc)
    return {"contracts_version": CONTRACTS_VERSION, "presence": presence}


@router.get("/social/history")
def get_social_history(
    filter: Literal[
        "all", "taunts_sent", "taunts_received", "mentions"
    ] = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=100),
    before: str | None = Query(default=None, max_length=64),
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        entries, next_before = list_social_history(
            conn, account_id, filter=filter, limit=limit, before=before
        )
    except SocialError as exc:
        _raise_social(exc)
    return {
        "contracts_version": CONTRACTS_VERSION,
        "filter": filter,
        "entries": entries,
        "history": entries,
        "next_before": next_before,
    }
