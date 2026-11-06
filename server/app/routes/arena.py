"""Battle arena: pending challenge inbox and deterministic Teknium practice.

Practice uses the authoritative ``battle-2`` engine so clients can render the
five-type chart, but it never changes ratings. Rewards follow the existing
practice rules (first three rewarded practice matches per UTC day).
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .. import CONTRACTS_VERSION, ECONOMY_VERSION
from ..combat import (
    BATTLE_2_VERSION,
    CombatError,
    SPECIES_STATS,
    SPECIES_TYPES,
    canonical_json,
    resolve_match,
    validate_tactic_card,
)
from ..db import account_exists, get_current_account_id, get_db, utc_now_iso
from ..matchmaking import reward_bridge

router = APIRouter(tags=["arena"])

PRACTICE_BOT_ID = "00000000-0000-4000-8000-00000000b07b"
PRACTICE_BOT_NAME = "Teknium"
PRACTICE_BOT_SPECIES = "byteblob"
PRACTICE_SEED_TAG = "arena.practice.v1"
PRACTICE_DAILY_REWARD_LIMIT = 3
PRACTICE_REWARD_BITS = 10
PRACTICE_REWARD_XP = 15

PRACTICE_BOT_TACTIC = {
    "ruleset_version": BATTLE_2_VERSION,
    "stance": "balanced",
    "actions": [
        {"when": {"self_hp_lte_pct": 40}, "move": "guard"},
        {"when": {"special_ready": True}, "move": "glitch_pulse"},
        {"when": {"always": True}, "move": "basic_attack"},
    ],
}


class PracticeRequest(BaseModel):
    pet_id: str = Field(min_length=1, max_length=64)
    tactics: dict[str, Any] | None = None
    model_config = ConfigDict(extra="ignore")


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _challenge_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "contracts_version": CONTRACTS_VERSION,
        "id": row["id"],
        "challenger_id": row["challenger_id"],
        "defender_id": row["defender_id"],
        "mode": row["mode"],
        "status": row["status"],
        "expires_at": row["expires_at"],
        "created_at": row["created_at"],
    }


def _practice_tactic(raw: Any) -> dict[str, Any]:
    try:
        return validate_tactic_card(raw, BATTLE_2_VERSION)
    except CombatError as exc:
        # The legacy single-player card used battle-1. Practice is the only
        # place we can safely upgrade it: ratings and persisted battle-1
        # replays are untouched.
        if (
            exc.code == "tactic_ruleset_mismatch"
            and isinstance(raw, dict)
            and raw.get("ruleset_version") == "battle-1"
        ):
            upgraded = dict(raw)
            upgraded["ruleset_version"] = BATTLE_2_VERSION
            try:
                return validate_tactic_card(upgraded, BATTLE_2_VERSION)
            except CombatError as retry_exc:
                raise _error(422, retry_exc.code, retry_exc.message) from retry_exc
        raise _error(422, exc.code, exc.message) from exc


def _practice_seed(pet_id: str, pet_species: str, card: dict[str, Any]) -> str:
    material = canonical_json(
        {
            "tag": PRACTICE_SEED_TAG,
            "pet_id": pet_id,
            "pet_species": pet_species,
            "bot_id": PRACTICE_BOT_ID,
            "bot_species": PRACTICE_BOT_SPECIES,
            "tactics": card,
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _effectiveness_label(numerator: int, denominator: int) -> str:
    if numerator * 1 > denominator:
        return "super"
    if numerator * 1 < denominator:
        return "resisted"
    return "neutral"


def _enrich_event(
    event: dict[str, Any], participants: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    enriched = dict(event)
    status = dict(event.get("status_delta") or {})
    actor = event.get("actor")
    defender = "b" if actor == "a" else "a"
    move_type = status.get("move_type")
    type_multiplier = status.get("type_multiplier")
    if not isinstance(type_multiplier, (list, tuple)) or len(type_multiplier) != 2:
        type_multiplier = None

    label = None
    multiplier = None
    if move_type and type_multiplier is not None:
        numerator = int(type_multiplier[0])
        denominator = int(type_multiplier[1])
        label = _effectiveness_label(numerator, denominator)
        multiplier = {
            "numerator": numerator,
            "denominator": denominator,
            "value": round(numerator / denominator, 4),
        }
        status["effectiveness"] = label
        status["effectiveness_multiplier"] = multiplier
        status["effectiveness_value"] = multiplier["value"]

    actor_info = participants.get(actor, {})
    defender_info = participants.get(defender, {})
    enriched.update(
        {
            "actor_name": actor_info.get("name"),
            "attacker_type": actor_info.get("type"),
            "defender_type": defender_info.get("type"),
            "move_type": move_type,
            "damage": int(status.get("damage") or 0),
            "effectiveness": label,
            "effectiveness_text": {
                "super": "Super effective",
                "resisted": "Not very effective",
                "neutral": "Neutral",
            }.get(label or ""),
            "multiplier": multiplier["value"] if multiplier else None,
            "multiplier_fraction": multiplier,
            "type_multiplier": list(type_multiplier)
            if type_multiplier is not None
            else None,
            "status_delta": status,
        }
    )
    return enriched


@router.get("/challenges/inbox")
def get_challenge_inbox(
    account_id: str = Depends(get_current_account_id),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    if not account_exists(conn, account_id):
        raise _error(401, "unauthorized", "A valid account session is required.")

    now = utc_now_iso()
    with conn:
        conn.execute(
            """
            UPDATE challenges SET status = 'expired'
            WHERE status = 'pending' AND expires_at <= ?
            """,
            (now,),
        )

    rows = conn.execute(
        """
        SELECT * FROM challenges
        WHERE status = 'pending'
          AND (challenger_id = ? OR defender_id = ?)
        ORDER BY created_at DESC, id ASC
        """,
        (account_id, account_id),
    ).fetchall()

    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []
    for row in rows:
        payload = _challenge_payload(row)
        if row["defender_id"] == account_id:
            payload["direction"] = "incoming"
            incoming.append(payload)
        else:
            payload["direction"] = "outgoing"
            outgoing.append(payload)

    combined = [*incoming, *outgoing]
    return {
        "contracts_version": CONTRACTS_VERSION,
        "incoming": incoming,
        "outgoing": outgoing,
        "challenges": combined,
        "pending": combined,
        "count": len(combined),
    }


@router.post("/practice")
def start_practice(
    payload: PracticeRequest,
    account_id: str = Depends(get_current_account_id),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    if not account_exists(conn, account_id):
        raise _error(401, "unauthorized", "A valid account session is required.")

    pet = conn.execute(
        "SELECT id, account_id, species, name FROM pets WHERE id = ?",
        (payload.pet_id,),
    ).fetchone()
    if pet is None:
        raise _error(404, "pet_not_found", "No pet exists for that id.")
    if pet["account_id"] != account_id:
        raise _error(403, "pet_not_owned", "That pet belongs to another account.")

    species = pet["species"]
    if species not in SPECIES_STATS:
        raise _error(422, "species_unknown", f"unknown species: {species!r}")
    pet_type = SPECIES_TYPES.get(species)
    bot_type = SPECIES_TYPES.get(PRACTICE_BOT_SPECIES)
    if pet_type is None or bot_type is None:
        raise _error(422, "type_unmapped", "That species has no battle-2 type.")

    card = _practice_tactic(payload.tactics)
    bot_card = validate_tactic_card(PRACTICE_BOT_TACTIC, BATTLE_2_VERSION)
    seed = _practice_seed(pet["id"], species, card)

    try:
        replay = resolve_match(
            BATTLE_2_VERSION,
            {"species": species},
            {"species": PRACTICE_BOT_SPECIES},
            card,
            bot_card,
            seed,
        )
    except CombatError as exc:
        raise _error(422, exc.code, exc.message) from exc

    participants = {
        "a": {"id": pet["id"], "name": pet["name"], "species": species, "type": pet_type},
        "b": {
            "id": PRACTICE_BOT_ID,
            "name": PRACTICE_BOT_NAME,
            "species": PRACTICE_BOT_SPECIES,
            "type": bot_type,
        },
    }
    turn_log = [_enrich_event(event, participants) for event in replay.events]

    challenge_id = str(uuid.uuid4())
    match_id = str(uuid.uuid4())
    now_dt = datetime.now(timezone.utc)
    now = utc_now_iso()
    expires_at = (
        (now_dt + timedelta(days=1))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    commitment = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    final_hp_json = canonical_json(replay.final_hp)

    prior_rewarded = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM matches AS m
        JOIN challenges AS c ON c.id = m.challenge_id
        WHERE m.status = 'resolved'
          AND c.mode = 'practice'
          AND c.challenger_id = ?
          AND substr(m.resolved_at, 1, 10) = ?
        """,
        (account_id, now[:10]),
    ).fetchone()["total"]
    awards: list[dict[str, Any]] = []
    if prior_rewarded < PRACTICE_DAILY_REWARD_LIMIT:
        awards = [
            {
                "account_id": account_id,
                "kind": "bits",
                "amount": PRACTICE_REWARD_BITS,
                "reason": "battle.practice.bits",
            },
            {
                "account_id": account_id,
                "kind": "xp",
                "amount": PRACTICE_REWARD_XP,
                "reason": "battle.practice.xp",
            },
        ]

    with conn:
        conn.execute(
            """
            INSERT INTO challenges (
                id, challenger_id, defender_id, mode, status, idempotency_key,
                expires_at, created_at
            ) VALUES (?, ?, ?, 'practice', 'accepted', NULL, ?, ?)
            """,
            (challenge_id, account_id, PRACTICE_BOT_ID, expires_at, now),
        )
        conn.execute(
            """
            INSERT INTO matches (
                id, challenge_id, ruleset_version, economy_version,
                seed_commitment, seed, status, replay_hash, winner, result,
                rounds, final_hp_json, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'resolved', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                challenge_id,
                BATTLE_2_VERSION,
                ECONOMY_VERSION,
                commitment,
                seed,
                replay.replay_hash,
                replay.winner,
                replay.result,
                replay.rounds,
                final_hp_json,
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO tactics (match_id, account_id, card_json, locked_at)
            VALUES (?, ?, ?, ?)
            """,
            (match_id, account_id, canonical_json(card), now),
        )
        conn.execute(
            """
            INSERT INTO tactics (match_id, account_id, card_json, locked_at)
            VALUES (?, ?, ?, ?)
            """,
            (match_id, PRACTICE_BOT_ID, canonical_json(bot_card), now),
        )
        for seq, event in enumerate(replay.events, start=1):
            conn.execute(
                """
                INSERT INTO match_events (match_id, seq, event_json)
                VALUES (?, ?, ?)
                """,
                (match_id, seq, canonical_json(event)),
            )
        receipts = (
            reward_bridge.award_match_rewards(conn, match_id, awards, now)
            if awards
            else []
        )

    match_payload = {
        "contracts_version": CONTRACTS_VERSION,
        "id": match_id,
        "challenge_id": challenge_id,
        "ruleset_version": BATTLE_2_VERSION,
        "economy_version": ECONOMY_VERSION,
        "seed_commitment": commitment,
        "seed": seed,
        "status": "resolved",
        "replay_hash": replay.replay_hash,
        "created_at": now,
        "resolved_at": now,
        "mode": "practice",
        "winner": replay.winner,
        "result": replay.result,
        "rounds": replay.rounds,
        "final_hp": dict(replay.final_hp),
        "pet": participants["a"],
        "bot": participants["b"],
    }
    replay_payload = replay.to_dict()

    return {
        "contracts_version": CONTRACTS_VERSION,
        "match_id": match_id,
        "match": match_payload,
        "replay": replay_payload,
        "turn_log": turn_log,
        "log": turn_log,
        "rewards": receipts,
        "bot": participants["b"],
    }
