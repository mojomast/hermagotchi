"""Challenge, tactics and authoritative match resolution service."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import CONTRACTS_VERSION, ECONOMY_VERSION, RULESET_VERSION
from ..combat import (
    CombatError,
    canonical_json,
    resolve_match,
    validate_tactic_card,
)
from ..db import utc_now_iso
from . import reward_bridge

MODES = ("practice", "casual", "ranked")
PRACTICE_BOT_ID = "00000000-0000-4000-8000-00000000b07b"
PRACTICE_BOT_SPECIES = "byteblob"
DEFAULT_EXPIRY_SECONDS = 7 * 24 * 60 * 60
PRACTICE_BOT_TACTIC = {
    "ruleset_version": RULESET_VERSION,
    "stance": "balanced",
    "actions": [
        {"when": {"self_hp_lte_pct": 40}, "move": "guard"},
        {"when": {"special_ready": True}, "move": "glitch_pulse"},
        {"when": {"always": True}, "move": "basic_attack"},
    ],
}


class MatchmakingError(Exception):
    def __init__(self, code: str, status_code: int, message: str):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message

    def to_detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _error(code: str, status_code: int, message: str) -> MatchmakingError:
    return MatchmakingError(code, status_code, message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


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


def _match_payload(row: sqlite3.Row) -> dict[str, Any]:
    resolved = row["status"] == "resolved"
    final_hp = None
    if resolved and row["final_hp_json"]:
        final_hp = json.loads(row["final_hp_json"])
    return {
        "contracts_version": CONTRACTS_VERSION,
        "id": row["id"],
        "challenge_id": row["challenge_id"],
        "ruleset_version": row["ruleset_version"],
        "economy_version": row["economy_version"],
        "seed_commitment": row["seed_commitment"],
        "seed": row["seed"] if resolved else None,
        "status": row["status"],
        "replay_hash": row["replay_hash"] if resolved else None,
        "winner": row["winner"] if resolved else None,
        "result": row["result"] if resolved else None,
        "rounds": (row["rounds"] or 0) if resolved else None,
        "final_hp": final_hp,
        "created_at": row["created_at"],
        "resolved_at": row["resolved_at"] if resolved else None,
    }


def _replay_payload(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any] | None:
    if row["status"] != "resolved" or not row["replay_hash"]:
        return None
    events = [
        json.loads(event["event_json"])
        for event in conn.execute(
            "SELECT event_json FROM match_events WHERE match_id = ? ORDER BY seq",
            (row["id"],),
        ).fetchall()
    ]
    final_hp = json.loads(row["final_hp_json"]) if row["final_hp_json"] else {}
    return {
        "ruleset_version": row["ruleset_version"],
        "seed": row["seed"],
        "replay_hash": row["replay_hash"],
        "rounds": row["rounds"] or 0,
        "winner": row["winner"],
        "result": row["result"],
        "final_hp": final_hp,
        "events": events,
    }


def _fetch_challenge(conn: sqlite3.Connection, challenge_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM challenges WHERE id = ?", (challenge_id,)
    ).fetchone()
    if row is None:
        raise _error("challenge_not_found", 404, "No challenge exists for that id.")
    return row


def _fetch_match(conn: sqlite3.Connection, match_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    if row is None:
        raise _error("match_not_found", 404, "No match exists for that id.")
    return row


def _account_exists(conn: sqlite3.Connection, account_id: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM accounts WHERE id = ? AND status = 'active'", (account_id,)
        ).fetchone()
        is not None
    )


def _normalize_defender_id(defender_id: str | None, mode: str) -> str:
    if mode == "practice":
        return PRACTICE_BOT_ID
    if not defender_id:
        raise _error("invalid_opponent", 422, "A defender_id is required.")
    value = defender_id.strip()
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise _error("invalid_opponent", 422, "defender_id must be a UUID.") from exc
    return value


def _deal_seed() -> tuple[str, str]:
    seed = secrets.token_hex(16)
    commitment = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return seed, commitment


def _create_match(conn: sqlite3.Connection, challenge: sqlite3.Row) -> sqlite3.Row:
    existing = conn.execute(
        "SELECT * FROM matches WHERE challenge_id = ?", (challenge["id"],)
    ).fetchone()
    if existing is not None:
        return existing

    seed, commitment = _deal_seed()
    match_id = str(uuid.uuid4())
    now = utc_now_iso()
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO matches (
            id, challenge_id, ruleset_version, economy_version, seed_commitment,
            seed, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (
            match_id,
            challenge["id"],
            RULESET_VERSION,
            ECONOMY_VERSION,
            commitment,
            seed,
            now,
        ),
    )
    if cursor.rowcount != 1:
        return _fetch_match(
            conn,
            conn.execute(
                "SELECT id FROM matches WHERE challenge_id = ?", (challenge["id"],)
            ).fetchone()["id"],
        )
    if challenge["mode"] == "practice":
        conn.execute(
            """
            INSERT OR IGNORE INTO tactics (match_id, account_id, card_json, locked_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                match_id,
                PRACTICE_BOT_ID,
                canonical_json(validate_tactic_card(PRACTICE_BOT_TACTIC)),
                now,
            ),
        )
    return _fetch_match(conn, match_id)


def create_challenge(
    conn: sqlite3.Connection,
    challenger_id: str,
    defender_id: str | None,
    mode: str,
    expires_in_s: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    if mode not in MODES:
        raise _error("mode_invalid", 422, "mode must be practice, casual or ranked.")
    if not _account_exists(conn, challenger_id):
        raise _error("unauthorized", 401, "A valid account session is required.")

    defender = _normalize_defender_id(defender_id, mode)
    if mode != "practice":
        if defender == challenger_id:
            raise _error("invalid_opponent", 422, "You cannot challenge yourself.")
        if not _account_exists(conn, defender):
            raise _error("opponent_not_found", 404, "That opponent does not exist.")

    if idempotency_key:
        existing = conn.execute(
            """
            SELECT * FROM challenges
            WHERE challenger_id = ? AND idempotency_key = ?
            """,
            (challenger_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            return _challenge_payload(existing)

    ttl = DEFAULT_EXPIRY_SECONDS
    if expires_in_s is not None:
        ttl = max(60, min(int(expires_in_s), 30 * 24 * 60 * 60))
    now_dt = _now()
    challenge_id = str(uuid.uuid4())
    status = "accepted" if mode == "practice" else "pending"

    try:
        with conn:
            conn.execute(
                """
                INSERT INTO challenges (
                    id, challenger_id, defender_id, mode, status, idempotency_key,
                    expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    challenge_id,
                    challenger_id,
                    defender,
                    mode,
                    status,
                    idempotency_key,
                    _iso(now_dt + timedelta(seconds=ttl)),
                    _iso(now_dt),
                ),
            )
            if mode == "practice":
                row = _fetch_challenge(conn, challenge_id)
                _create_match(conn, row)
    except sqlite3.IntegrityError:
        if idempotency_key:
            existing = conn.execute(
                """
                SELECT * FROM challenges
                WHERE challenger_id = ? AND idempotency_key = ?
                """,
                (challenger_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                return _challenge_payload(existing)
        raise

    return _challenge_payload(_fetch_challenge(conn, challenge_id))


def _expire_if_needed(conn: sqlite3.Connection, challenge: sqlite3.Row) -> sqlite3.Row:
    if challenge["status"] != "pending":
        return challenge
    if _parse_iso(challenge["expires_at"]) <= _now():
        with conn:
            conn.execute(
                "UPDATE challenges SET status = 'expired' WHERE id = ? AND status = 'pending'",
                (challenge["id"],),
            )
        return _fetch_challenge(conn, challenge["id"])
    return challenge


def respond_to_challenge(
    conn: sqlite3.Connection,
    challenge_id: str,
    account_id: str,
    action: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if action not in ("accept", "decline"):
        raise _error("action_invalid", 422, "action must be accept or decline.")

    challenge = _fetch_challenge(conn, challenge_id)
    is_practice = challenge["mode"] == "practice"
    allowed = (
        {challenge["challenger_id"], challenge["defender_id"]}
        if is_practice
        else {challenge["defender_id"]}
    )
    if account_id not in allowed:
        raise _error("not_defender", 403, "Only the challenged account may respond.")

    challenge = _expire_if_needed(conn, challenge)
    if challenge["status"] == "expired":
        raise _error("challenge_expired", 409, "This challenge has expired.")
    if challenge["status"] == "declined":
        if action == "decline":
            return _challenge_payload(challenge), None
        raise _error("challenge_not_pending", 409, "This challenge was declined.")
    if challenge["status"] == "resolved":
        match = conn.execute(
            "SELECT * FROM matches WHERE challenge_id = ?", (challenge["id"],)
        ).fetchone()
        return _challenge_payload(challenge), _match_payload(match) if match else None

    if action == "decline":
        with conn:
            conn.execute(
                "UPDATE challenges SET status = 'declined' WHERE id = ? AND status = 'pending'",
                (challenge["id"],),
            )
        return _challenge_payload(_fetch_challenge(conn, challenge["id"])), None

    with conn:
        conn.execute(
            "UPDATE challenges SET status = 'accepted' WHERE id = ? AND status = 'pending'",
            (challenge["id"],),
        )
        current = _fetch_challenge(conn, challenge["id"])
        match = _create_match(conn, current)

    return _challenge_payload(current), _match_payload(match)


def _load_tactics(conn: sqlite3.Connection, match_id: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT account_id, card_json FROM tactics WHERE match_id = ?", (match_id,)
    ).fetchall()
    return {row["account_id"]: json.loads(row["card_json"]) for row in rows}


def _pet_species(conn: sqlite3.Connection, account_id: str) -> str:
    row = conn.execute(
        "SELECT species FROM pets WHERE account_id = ?", (account_id,)
    ).fetchone()
    if row is None:
        raise _error("pet_not_found", 409, "Both accounts need an adopted pet.")
    return row["species"]


def _first_casual_today(
    conn: sqlite3.Connection, account_id: str, match_id: str, day: str
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM matches m
        JOIN challenges c ON c.id = m.challenge_id
        WHERE m.id != ?
          AND m.status = 'resolved'
          AND c.mode = 'casual'
          AND (c.challenger_id = ? OR c.defender_id = ?)
          AND substr(m.resolved_at, 1, 10) = ?
        LIMIT 1
        """,
        (match_id, account_id, account_id, day),
    ).fetchone()
    return row is None


def _reward_awards(
    conn: sqlite3.Connection,
    challenge: sqlite3.Row,
    match: sqlite3.Row,
    winner: str | None,
    now_iso: str,
) -> list[dict[str, Any]]:
    mode = challenge["mode"]
    if mode == "practice":
        # Daily/weekly caps are enforced atomically by the reward bridge.
        return [
            {
                "account_id": challenge["challenger_id"],
                "kind": "bits",
                "amount": 50,
                "reason": "battle.practice.bits",
                "mode": "practice",
            },
            {
                "account_id": challenge["challenger_id"],
                "kind": "xp",
                "amount": 15,
                "reason": "battle.practice.xp",
                "mode": "practice",
            },
        ]

    accounts = (challenge["challenger_id"], challenge["defender_id"])
    awards: list[dict[str, Any]] = []
    day = now_iso[:10]
    for index, (side, account_id) in enumerate(zip(("a", "b"), accounts)):
        opponent_id = accounts[1 - index]
        if mode == "ranked":
            won = winner == side
            bits, xp = (100, 60) if won else (25, 35)
            label = "win" if won else "loss"
        else:
            won = winner == side
            bits, xp = (80, 50) if won else (20, 30)
            if _first_casual_today(conn, account_id, match["id"], day):
                bits += 50
                xp += 30
            label = "win" if won else "loss"
        awards.append(
            {
                "account_id": account_id,
                "kind": "bits",
                "amount": bits,
                "reason": f"battle.{mode}.{label}.bits",
                "mode": mode,
                "opponent_id": opponent_id,
            }
        )
        awards.append(
            {
                "account_id": account_id,
                "kind": "xp",
                "amount": xp,
                "reason": f"battle.{mode}.{label}.xp",
                "mode": mode,
                "opponent_id": opponent_id,
            }
        )
    return awards


CAP_REASONS = (
    "practice.daily_cap",
    "practice.weekly_cap",
    "pvp.daily_cap",
    "pvp.opponent_daily_cap",
)


def _reward_status_for(
    conn: sqlite3.Connection, match_id: str, account_id: str
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT reason FROM ledger
        WHERE source_event_id = ? AND reason IN (?, ?, ?, ?)
        LIMIT 1
        """,
        (f"match:{match_id}:{account_id}:bits", *CAP_REASONS),
    ).fetchone()
    if row is None:
        return {}
    return {"reward_status": "capped", "reward_reason": row["reason"]}


def _match_payload_for(
    conn: sqlite3.Connection, row: sqlite3.Row, account_id: str
) -> dict[str, Any]:
    payload = _match_payload(row)
    payload.update(_reward_status_for(conn, row["id"], account_id))
    return payload


def _update_ratings_if_present(
    conn: sqlite3.Connection, challenge: sqlite3.Row, winner: str | None
) -> None:
    if challenge["mode"] not in {"casual", "ranked"}:
        return
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ratings'"
    ).fetchone()
    if table is None:
        return
    columns = {row[1] for row in conn.execute("PRAGMA table_info(ratings)")}
    if not {"account_id", "season_id", "rating", "wins", "losses"} <= columns:
        return

    season = "season-1"
    accounts = (challenge["challenger_id"], challenge["defender_id"])
    if winner == "a":
        scores = (1.0, 0.0)
    elif winner == "b":
        scores = (0.0, 1.0)
    else:
        scores = (0.5, 0.5)

    def extract(account_id: str) -> tuple[int, int, int]:
        row = conn.execute(
            """
            SELECT rating, wins, losses FROM ratings
            WHERE account_id = ? AND season_id = ?
            """,
            (account_id, season),
        ).fetchone()
        if row is None:
            return 1000, 0, 0
        return row["rating"], row["wins"], row["losses"]

    def store(account_id: str, rating: int, wins: int, losses: int) -> None:
        exists = conn.execute(
            """
            SELECT 1 FROM ratings WHERE account_id = ? AND season_id = ?
            """,
            (account_id, season),
        ).fetchone()
        if exists is None:
            conn.execute(
                """
                INSERT INTO ratings (account_id, season_id, rating, wins, losses)
                VALUES (?, ?, ?, ?, ?)
                """,
                (account_id, season, rating, wins, losses),
            )
        else:
            conn.execute(
                """
                UPDATE ratings SET rating = ?, wins = ?, losses = ?
                WHERE account_id = ? AND season_id = ?
                """,
                (rating, wins, losses, account_id, season),
            )

    ratings: list[tuple[int, int, int]] = []
    for account_id in accounts:
        ratings.append(extract(account_id))

    for index, account_id in enumerate(accounts):
        opponent_index = 1 - index
        rating, wins, losses = ratings[index]
        opponent_rating = ratings[opponent_index][0]
        games = wins + losses
        k = 24 if games < 10 else 16
        expected = 1 / (1 + 10 ** ((opponent_rating - rating) / 400))
        score = scores[index]
        new_rating = max(0, round(rating + k * (score - expected)))
        if score >= 1.0:
            wins += 1
        elif score <= 0.0:
            losses += 1
        store(account_id, new_rating, wins, losses)


def resolve_pending_match(
    conn: sqlite3.Connection, match_id: str
) -> tuple[sqlite3.Row, dict[str, Any] | None]:
    match = _fetch_match(conn, match_id)
    if match["status"] != "pending":
        return match, _replay_payload(conn, match)
    challenge = _fetch_challenge(conn, match["challenge_id"])
    cards = _load_tactics(conn, match_id)

    if challenge["mode"] == "practice":
        card_a = cards.get(challenge["challenger_id"])
        card_b = cards.get(PRACTICE_BOT_ID)
        species_a = _pet_species(conn, challenge["challenger_id"])
        species_b = PRACTICE_BOT_SPECIES
    else:
        card_a = cards.get(challenge["challenger_id"])
        card_b = cards.get(challenge["defender_id"])
        if card_a is None or card_b is None:
            return match, None
        species_a = _pet_species(conn, challenge["challenger_id"])
        species_b = _pet_species(conn, challenge["defender_id"])

    if card_a is None:
        return match, None

    try:
        replay = resolve_match(
            RULESET_VERSION,
            {"species": species_a},
            {"species": species_b},
            card_a,
            card_b,
            match["seed"],
        )
    except CombatError as exc:
        raise _error(exc.code, 422, exc.message) from exc

    now_iso = utc_now_iso()
    final_hp_json = canonical_json(replay.final_hp)
    with conn:
        cursor = conn.execute(
            """
            UPDATE matches SET
                status = 'resolved', replay_hash = ?, winner = ?, result = ?,
                rounds = ?, final_hp_json = ?, resolved_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (
                replay.replay_hash,
                replay.winner,
                replay.result,
                replay.rounds,
                final_hp_json,
                now_iso,
                match_id,
            ),
        )
        if cursor.rowcount != 1:
            current = _fetch_match(conn, match_id)
            return current, _replay_payload(conn, current)
        for seq, event in enumerate(replay.events, start=1):
            conn.execute(
                """
                INSERT OR IGNORE INTO match_events (match_id, seq, event_json)
                VALUES (?, ?, ?)
                """,
                (match_id, seq, canonical_json(event)),
            )
        conn.execute(
            "UPDATE challenges SET status = 'resolved' WHERE id = ?",
            (challenge["id"],),
        )
        _update_ratings_if_present(conn, challenge, replay.winner)
        updated = _fetch_match(conn, match_id)
        awards = _reward_awards(conn, challenge, updated, replay.winner, now_iso)
        receipts = reward_bridge.award_match_rewards(conn, match_id, awards, now_iso)

    replay_payload = replay.to_dict()
    replay_payload["rewards"] = receipts
    return _fetch_match(conn, match_id), replay_payload


def submit_tactics(
    conn: sqlite3.Connection,
    match_id: str,
    account_id: str,
    card: Any,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    match = _fetch_match(conn, match_id)
    challenge = _fetch_challenge(conn, match["challenge_id"])
    participants = {challenge["challenger_id"], challenge["defender_id"]}
    if account_id not in participants:
        raise _error("not_participant", 403, "Only match participants may submit tactics.")
    if challenge["status"] == "pending":
        raise _error("match_not_ready", 409, "The challenge has not been accepted.")
    if challenge["status"] == "expired" or match["status"] == "expired":
        raise _error("match_expired", 409, "This match has expired.")

    try:
        normalized = validate_tactic_card(card)
    except CombatError as exc:
        raise _error(exc.code, 422, exc.message) from exc
    encoded = canonical_json(normalized)

    existing = conn.execute(
        "SELECT card_json FROM tactics WHERE match_id = ? AND account_id = ?",
        (match_id, account_id),
    ).fetchone()
    if existing is not None:
        if canonical_json(json.loads(existing["card_json"])) == encoded:
            current, replay = resolve_pending_match(conn, match_id)
            if isinstance(replay, dict):
                replay.update(_reward_status_for(conn, match_id, account_id))
            return _match_payload_for(conn, current, account_id), replay
        raise _error("tactics_locked", 409, "Tactics are already locked for this match.")
    if match["status"] != "pending":
        raise _error("match_resolved", 409, "This match is no longer accepting tactics.")

    with conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO tactics (match_id, account_id, card_json, locked_at)
            VALUES (?, ?, ?, ?)
            """,
            (match_id, account_id, encoded, utc_now_iso()),
        )
        if cursor.rowcount != 1:
            locked = conn.execute(
                "SELECT card_json FROM tactics WHERE match_id = ? AND account_id = ?",
                (match_id, account_id),
            ).fetchone()
            if locked is None or canonical_json(json.loads(locked["card_json"])) != encoded:
                raise _error(
                    "tactics_locked", 409, "Tactics are already locked for this match."
                )

    match, replay = resolve_pending_match(conn, match_id)
    if isinstance(replay, dict):
        replay.update(_reward_status_for(conn, match_id, account_id))
    return _match_payload_for(conn, match, account_id), replay


def get_match(
    conn: sqlite3.Connection, match_id: str, account_id: str
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    match = _fetch_match(conn, match_id)
    challenge = _fetch_challenge(conn, match["challenge_id"])
    if account_id not in {challenge["challenger_id"], challenge["defender_id"]}:
        raise _error("not_participant", 403, "Only match participants may read this match.")
    replay = _replay_payload(conn, match)
    if isinstance(replay, dict):
        replay.update(_reward_status_for(conn, match_id, account_id))
    return _match_payload_for(conn, match, account_id), replay
