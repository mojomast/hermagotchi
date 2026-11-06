"""Read-only catalog projection for contracts-v1 Item payloads."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .. import ASSET_PACK_VERSION, CONTRACTS_VERSION

SLOTS = ("head", "face", "back", "front", "aura", "emote", "habitat", "title")


def _rigs(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [value for value in parsed if isinstance(value, str)]


def item_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "contracts_version": CONTRACTS_VERSION,
        "id": row["id"],
        "name": row["name"],
        "slot": row["slot"],
        "rarity": row["rarity"],
        "price_bits": row["price_bits"],
        "asset_id": row["asset_id"],
        "compatible_rigs": _rigs(row["compatible_rigs_json"]),
        "catalog_version": row["catalog_version"],
        "active": bool(row["active"]),
    }


def get_item(conn: sqlite3.Connection, item_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()


def list_catalog(conn: sqlite3.Connection, *, active_only: bool = True) -> dict[str, Any]:
    query = "SELECT * FROM items"
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY slot, id"
    rows = conn.execute(query).fetchall()
    items = [item_payload(row) for row in rows]
    version = items[0]["catalog_version"] if items else ASSET_PACK_VERSION
    return {
        "contracts_version": CONTRACTS_VERSION,
        "catalog_version": version,
        "items": items,
    }
