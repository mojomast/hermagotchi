"""Atomic purchase and equip routes."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..db import account_exists, get_current_account_id, get_db
from ..economy import EconomyError
from ..shop import ShopError, equip_item, purchase_item

router = APIRouter(tags=["shop"])


class PurchaseRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    idempotency_key: str | None = Field(default=None, max_length=128)
    model_config = ConfigDict(extra="ignore")


class EquipRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    slot: str | None = Field(default=None, max_length=16)
    idempotency_key: str | None = Field(default=None, max_length=128)
    model_config = ConfigDict(extra="ignore")


def _require_account(conn: Connection, account_id: str) -> None:
    if not account_exists(conn, account_id):
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "A valid account session is required."},
        )


def _raise_shop(exc: ShopError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.to_detail())


@router.post("/shop/purchases", status_code=201)
def create_purchase(
    payload: PurchaseRequest,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        return purchase_item(
            conn,
            account_id,
            payload.item_id,
            payload.idempotency_key or idempotency_header,
        )
    except ShopError as exc:
        _raise_shop(exc)
    except EconomyError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@router.post("/pets/{pet_id}/equip")
def equip(
    pet_id: str,
    payload: EquipRequest,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    try:
        return equip_item(
            conn,
            account_id,
            pet_id,
            payload.item_id,
            payload.idempotency_key or idempotency_header,
            payload.slot,
        )
    except ShopError as exc:
        _raise_shop(exc)
