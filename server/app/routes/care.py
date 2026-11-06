"""Owner care actions and equipment removal (HGT-W8-S).

Feed/play/rest are server-authoritative: meters are clamped to 0-100, each
action has its own cooldown, and a repeated ``Idempotency-Key`` replays the
original receipt instead of applying a second care tick. Unequip is naturally
idempotent because removing an already-empty slot is a no-op.

The route file only uses the existing pets/equipment tables plus the
forward-only ``care_events`` receipt ledger from migration 0008.
"""

from __future__ import annotations

import json
import math
import sqlite3
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .. import CONTRACTS_VERSION
from ..auth import iso_from_ts, now_ts, ts_from_iso
from ..db import account_exists, get_current_account_id, get_db
from ..shop import loadout_for_pet
from ..shop.transactions import write_transaction
from .pets import _private_pet

router = APIRouter(tags=["pets"])

CareAction = Literal["feed", "play", "rest"]
Slot = Literal["head", "face", "back", "front", "aura", "emote", "habitat", "title"]

MAX_IDEMPOTENCY_LEN = 128

# Care never punishes a pet into an unrecoverable state; it only nudges the
# bounded meters. Values intentionally mirror the client's optimistic preview.
CARE_EFFECTS: dict[str, dict[str, int]] = {
    "feed": {"hunger": 25},
    "play": {"comfort": 20, "energy": -10},
    "rest": {"energy": 25},
}

# Per-action cooldowns in seconds. Tests may patch these values.
CARE_COOLDOWN_S: dict[str, int] = {
    "feed": 300,
    "play": 300,
    "rest": 300,
}

CARE_FIELDS = ("health", "comfort", "hunger", "energy")


class CareRequest(BaseModel):
    action: CareAction
    idempotency_key: str | None = Field(default=None, max_length=MAX_IDEMPOTENCY_LEN)
    model_config = ConfigDict(extra="ignore")


class UnequipRequest(BaseModel):
    slot: Slot
    idempotency_key: str | None = Field(default=None, max_length=MAX_IDEMPOTENCY_LEN)
    model_config = ConfigDict(extra="ignore")


def _require_account(conn: sqlite3.Connection, account_id: str) -> None:
    if not account_exists(conn, account_id):
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "A valid account session is required."},
        )


def _normalise_key(value: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "code": "idempotency_key_required",
                "message": "A non-empty idempotency_key is required.",
            },
        )
    key = value.strip()
    if len(key) > MAX_IDEMPOTENCY_LEN:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "idempotency_key_required",
                "message": (
                    f"idempotency_key must be at most {MAX_IDEMPOTENCY_LEN} characters."
                ),
            },
        )
    return key


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def _apply_care(care: dict[str, Any], action: str) -> dict[str, int]:
    updated = {field: _clamp(int(care.get(field, 0) or 0)) for field in CARE_FIELDS}
    for field, delta in CARE_EFFECTS[action].items():
        updated[field] = _clamp(updated[field] + delta)
    return updated


def _pet_row(conn: sqlite3.Connection, pet_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()


def _cooled_down(conn: sqlite3.Connection, pet_id: str, action: str, now: float) -> int:
    row = conn.execute(
        """
        SELECT cooldown_until FROM care_events
        WHERE pet_id = ? AND action = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (pet_id, action),
    ).fetchone()
    if row is None:
        return 0
    try:
        until = ts_from_iso(row["cooldown_until"])
    except (TypeError, ValueError):
        return 0
    if until <= now:
        return 0
    return max(1, int(math.ceil(until - now)))


@router.post("/pets/{pet_id}/care")
def care_for_pet(
    pet_id: str,
    payload: CareRequest,
    account_id: str = Depends(get_current_account_id),
    conn: sqlite3.Connection = Depends(get_db),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    _require_account(conn, account_id)
    key = _normalise_key(payload.idempotency_key or idempotency_header)

    with write_transaction(conn):
        pet = _pet_row(conn, pet_id)
        if pet is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "pet_not_found", "message": "No pet exists for that id."},
            )
        if pet["account_id"] != account_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "pet_not_owned",
                    "message": "This pet belongs to another account.",
                },
            )

        existing = conn.execute(
            "SELECT * FROM care_events WHERE account_id = ? AND idempotency_key = ?",
            (account_id, key),
        ).fetchone()
        if existing is not None:
            if existing["pet_id"] != pet_id or existing["action"] != payload.action:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "idempotency_conflict",
                        "message": "That idempotency key was already used for different care.",
                    },
                )
            replay = json.loads(existing["result_json"])
            replay["duplicate"] = True
            return replay

        moment = now_ts()
        retry_after = _cooled_down(conn, pet_id, payload.action, moment)
        if retry_after:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "care_cooldown",
                    "message": "That care action is still cooling down.",
                    "retry_after_s": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        care = _apply_care(json.loads(pet["care_json"]), payload.action)
        revision = int(pet["revision"]) + 1
        cared_at = iso_from_ts(moment)
        cooldown_until = iso_from_ts(moment + CARE_COOLDOWN_S[payload.action])
        event_id = str(uuid.uuid4())

        conn.execute(
            """
            UPDATE pets
            SET care_json = ?, care_updated_at = ?, revision = ?
            WHERE id = ?
            """,
            (json.dumps(care, sort_keys=True), cared_at, revision, pet_id),
        )
        updated = _pet_row(conn, pet_id)
        result: dict[str, Any] = {
            "contracts_version": CONTRACTS_VERSION,
            "pet_id": pet_id,
            "action": payload.action,
            "duplicate": False,
            "cooldown_until": cooldown_until,
            "care": care,
            "revision": revision,
            "receipt": {
                "receipt_id": event_id,
                "pet_id": pet_id,
                "action": payload.action,
                "care": dict(care),
                "pet_revision": revision,
                "at": cared_at,
                "cooldown_until": cooldown_until,
            },
            "pet": _private_pet(updated),
        }
        conn.execute(
            """
            INSERT INTO care_events (
                id, pet_id, account_id, action, idempotency_key, care_json,
                care_updated_at, cooldown_until, result_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                pet_id,
                account_id,
                payload.action,
                key,
                json.dumps(care, sort_keys=True),
                cared_at,
                cooldown_until,
                json.dumps(result, sort_keys=True),
                cared_at,
            ),
        )
        return result


@router.post("/pets/{pet_id}/unequip")
def unequip_from_pet(
    pet_id: str,
    payload: UnequipRequest,
    account_id: str = Depends(get_current_account_id),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_account(conn, account_id)

    with write_transaction(conn):
        pet = _pet_row(conn, pet_id)
        if pet is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "pet_not_found", "message": "No pet exists for that id."},
            )
        if pet["account_id"] != account_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "pet_not_owned",
                    "message": "This pet belongs to another account.",
                },
            )

        existing = conn.execute(
            "SELECT item_id FROM equipment WHERE pet_id = ? AND slot = ?",
            (pet_id, payload.slot),
        ).fetchone()
        if existing is not None:
            conn.execute(
                "DELETE FROM equipment WHERE pet_id = ? AND slot = ?",
                (pet_id, payload.slot),
            )

        return {
            "contracts_version": CONTRACTS_VERSION,
            "pet_id": pet_id,
            "slot": payload.slot,
            "unequipped_item_id": existing["item_id"] if existing is not None else None,
            "duplicate": existing is None,
            "loadout": loadout_for_pet(conn, pet_id),
        }
