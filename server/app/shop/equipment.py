"""Ownership- and compatibility-checked pet equipment."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .. import CONTRACTS_VERSION
from ..db import utc_now_iso
from .catalog import get_item, item_payload
from .errors import (
    ItemInactive,
    ItemIncompatible,
    ItemNotFound,
    ItemNotOwned,
    PetNotFound,
    PetNotOwned,
    SlotIncompatible,
)
from .purchases import normalise_key
from .transactions import write_transaction

PET_RIG_FAMILY = "small_front_v1"


def _rigs(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [value for value in parsed if isinstance(value, str)]


def loadout_for_pet(conn: sqlite3.Connection, pet_id: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT i.*, e.slot AS equipped_slot, e.equipped_at
        FROM equipment e
        JOIN items i ON i.id = e.item_id
        WHERE e.pet_id = ?
        ORDER BY e.slot
        """,
        (pet_id,),
    ).fetchall()
    return {row["equipped_slot"]: item_payload(row) for row in rows}


def equip_item(
    conn: sqlite3.Connection,
    account_id: str,
    pet_id: str,
    item_id: str,
    idempotency_key: str | None,
    slot: str | None = None,
) -> dict[str, Any]:
    normalise_key(idempotency_key)

    with write_transaction(conn):
        pet = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
        if pet is None:
            raise PetNotFound("No pet exists for that id.")
        if pet["account_id"] != account_id:
            raise PetNotOwned("This pet belongs to another account.")

        item_row = get_item(conn, item_id)
        if item_row is None:
            raise ItemNotFound("No item exists for that id.")
        if not bool(item_row["active"]):
            raise ItemInactive("That item is no longer available.")

        requested_slot = (slot or "").strip() or item_row["slot"]
        if requested_slot != item_row["slot"]:
            raise SlotIncompatible("That item cannot be equipped in the requested slot.")
        if PET_RIG_FAMILY not in _rigs(item_row["compatible_rigs_json"]):
            raise ItemIncompatible("That item is not compatible with this pet's rig.")

        owned = conn.execute(
            "SELECT 1 FROM inventory WHERE account_id = ? AND item_id = ?",
            (account_id, item_id),
        ).fetchone()
        if owned is None:
            raise ItemNotOwned("Purchase that item before equipping it.")

        existing = conn.execute(
            "SELECT * FROM equipment WHERE pet_id = ? AND slot = ?",
            (pet_id, item_row["slot"]),
        ).fetchone()
        duplicate = existing is not None and existing["item_id"] == item_id
        equipped_at = utc_now_iso()
        if not duplicate:
            conn.execute(
                """
                INSERT INTO equipment (pet_id, slot, item_id, equipped_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (pet_id, slot) DO UPDATE SET
                    item_id = excluded.item_id,
                    equipped_at = excluded.equipped_at
                """,
                (pet_id, item_row["slot"], item_id, equipped_at),
            )
        else:
            equipped_at = existing["equipped_at"]

        return {
            "contracts_version": CONTRACTS_VERSION,
            "pet_id": pet_id,
            "slot": item_row["slot"],
            "equipped_item_id": item_id,
            "equipped_at": equipped_at,
            "duplicate": duplicate,
            "item": item_payload(item_row),
            "loadout": loadout_for_pet(conn, pet_id),
        }
