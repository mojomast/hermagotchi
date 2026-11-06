"""Public ranked leaderboard slice with a personal near-rank window.

Ranking is deterministic: rating DESC, wins DESC, losses ASC, account_id ASC.
The payload deliberately contains no email/credential fields and pet display
uses only species, name and equipped item ids (never image bytes or URLs).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Query

from .. import CONTRACTS_VERSION
from ..db import get_current_account_id_optional, get_db

router = APIRouter(tags=["leaderboard"])

RANKING_VERSION = "rating-1"


def _public_handle(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    handle = value.strip()
    if not handle or "@" in handle:
        return None
    return handle[:64]


def _loadout(conn: sqlite3.Connection, pet_id: str | None) -> dict[str, str]:
    if not pet_id:
        return {}
    rows = conn.execute(
        "SELECT slot, item_id FROM equipment WHERE pet_id = ? ORDER BY slot",
        (pet_id,),
    ).fetchall()
    return {row["slot"]: row["item_id"] for row in rows}


def _pet_display(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any] | None:
    if not row["pet_id"]:
        return None
    return {
        "id": row["pet_id"],
        "species": row["species"],
        "name": row["name"],
        "loadout": _loadout(conn, row["pet_id"]),
    }


def _ranked_rows(conn: sqlite3.Connection, season_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            r.account_id,
            r.season_id,
            r.rating,
            r.wins,
            r.losses,
            a.public_handle,
            p.id AS pet_id,
            p.species AS species,
            p.name AS name
        FROM ratings AS r
        JOIN accounts AS a ON a.id = r.account_id
        LEFT JOIN pets AS p ON p.account_id = r.account_id
        WHERE r.season_id = ? AND a.status = 'active'
        ORDER BY r.rating DESC, r.wins DESC, r.losses ASC, r.account_id ASC
        """,
        (season_id,),
    ).fetchall()


@router.get("/leaderboard")
def get_leaderboard(
    season_id: str = Query(default="season-1", min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    near: int = Query(default=2, ge=0, le=25),
    account_id: str | None = Depends(get_current_account_id_optional),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    rows = _ranked_rows(conn, season_id)
    ranked: list[dict[str, Any]] = []
    for rank, row in enumerate(rows, start=1):
        ranked.append(
            {
                "rank": rank,
                "season_id": row["season_id"],
                "account": {
                    "id": row["account_id"],
                    "public_handle": _public_handle(row["public_handle"]),
                },
                "rating": row["rating"],
                "wins": row["wins"],
                "losses": row["losses"],
                "pet": _pet_display(conn, row),
            }
        )

    me = next(
        (entry for entry in ranked if entry["account"]["id"] == account_id),
        None,
    )
    near_rank: list[dict[str, Any]] = []
    if me is not None:
        index = int(me["rank"]) - 1
        start = max(0, index - near)
        end = min(len(ranked), index + near + 1)
        near_rank = ranked[start:end]

    return {
        "contracts_version": CONTRACTS_VERSION,
        "ranking_version": RANKING_VERSION,
        "season_id": season_id,
        "total": len(ranked),
        "offset": offset,
        "limit": limit,
        "entries": ranked[offset : offset + limit],
        "me": me,
        "near_rank": near_rank,
    }
