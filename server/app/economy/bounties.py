"""Server-owned daily bounties and one-time claims."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .. import CONTRACTS_VERSION
from ..db import utc_now_iso
from .errors import BountyNotActive, BountyNotFound, BountyNotEligible
from .ledger import credit, ledger_payload, wallet_payload, write_transaction


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _reward(row: sqlite3.Row) -> dict[str, int]:
    data = _json(row["reward_json"], {})
    if not isinstance(data, dict):
        data = {}
    bits = data.get("bits", data.get("reward_bits", 0))
    xp = data.get("xp", data.get("reward_xp", 0))
    try:
        bits = max(0, int(bits))
    except (TypeError, ValueError):
        bits = 0
    try:
        xp = max(0, int(xp))
    except (TypeError, ValueError):
        xp = 0
    return {"bits": bits, "xp": xp}


def _in_window(row: sqlite3.Row, now: datetime) -> bool:
    starts_at = _parse_ts(row["starts_at"])
    expires_at = _parse_ts(row["expires_at"])
    if starts_at is not None and now < starts_at:
        return False
    if expires_at is not None and now >= expires_at:
        return False
    return True


def _requirements_met(
    conn: sqlite3.Connection, account_id: str, row: sqlite3.Row, now: datetime
) -> bool:
    rule = _json(row["rule_json"], {})
    if not isinstance(rule, dict):
        return True
    rule_type = str(rule.get("type") or rule.get("kind") or "").strip()
    if not rule_type or rule_type in {"always", "daily", "daily_checkin", "manual"}:
        return True

    starts_at = row["starts_at"] or ""
    expires_at = row["expires_at"] or ""
    if rule_type in {"ledger_reason_count", "ledger_count"}:
        reason = str(rule.get("reason") or "")
        minimum = int(rule.get("min") or rule.get("count") or 1)
        found = conn.execute(
            """
            SELECT COUNT(*) AS n FROM ledger
            WHERE account_id = ? AND reason = ?
              AND created_at >= ? AND created_at < ?
            """,
            (account_id, reason, starts_at, expires_at),
        ).fetchone()["n"]
        return found >= minimum
    if rule_type in {"ledger_reason_sum", "ledger_sum"}:
        reason = str(rule.get("reason") or "")
        minimum = int(rule.get("min") or rule.get("bits") or 1)
        found = conn.execute(
            """
            SELECT COALESCE(SUM(delta), 0) AS total FROM ledger
            WHERE account_id = ? AND reason = ?
              AND created_at >= ? AND created_at < ?
            """,
            (account_id, reason, starts_at, expires_at),
        ).fetchone()["total"]
        return found >= minimum
    if rule_type in {"min_balance", "wallet_balance"}:
        minimum = int(rule.get("min") or rule.get("bits") or 0)
        wallet = conn.execute(
            "SELECT balance FROM wallets WHERE account_id = ?", (account_id,)
        ).fetchone()
        return (wallet["balance"] if wallet else 0) >= minimum

    # Server-seeded bounties are trusted; predicates that belong to a later
    # matchmaking slice are not client-invented and remain claimable here.
    return True


def _claim_row(
    conn: sqlite3.Connection, account_id: str, bounty_id: str
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM bounty_claims WHERE account_id = ? AND bounty_id = ?",
        (account_id, bounty_id),
    ).fetchone()


def _bounty_payload(
    row: sqlite3.Row, claim: sqlite3.Row | None, claimable: bool
) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"] or row["id"],
        "description": row["description"] or "",
        "starts_at": row["starts_at"],
        "expires_at": row["expires_at"],
        "rule": _json(row["rule_json"], {}),
        "reward": _reward(row),
        "max_claims": row["max_claims"],
        "active": bool(row["active"]),
        "claimed": claim is not None,
        "claimed_at": claim["claimed_at"] if claim is not None else None,
        "claimable": claimable,
        "ruleset_version": "battle-1",
        "contracts_version": CONTRACTS_VERSION,
    }


def list_bounties(
    conn: sqlite3.Connection, account_id: str, now: datetime | None = None
) -> list[dict[str, Any]]:
    current = _now(now)
    rows = conn.execute(
        "SELECT * FROM bounties WHERE active = 1 ORDER BY starts_at, id"
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        if not _in_window(row, current):
            continue
        claim = _claim_row(conn, account_id, row["id"])
        claimable = claim is None and _requirements_met(conn, account_id, row, current)
        result.append(_bounty_payload(row, claim, claimable))
    return result


def _claim_receipt(conn: sqlite3.Connection, claim: sqlite3.Row) -> dict[str, Any] | None:
    if not claim["ledger_id"]:
        return None
    row = conn.execute("SELECT * FROM ledger WHERE id = ?", (claim["ledger_id"],)).fetchone()
    return ledger_payload(row) if row is not None else None


def claim_bounty(
    conn: sqlite3.Connection,
    bounty_id: str,
    account_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = _now(now)
    with write_transaction(conn):
        row = conn.execute("SELECT * FROM bounties WHERE id = ?", (bounty_id,)).fetchone()
        if row is None:
            raise BountyNotFound("No bounty exists for that id.")
        if not bool(row["active"]) or not _in_window(row, current):
            raise BountyNotActive("That bounty is not currently active.")

        existing = _claim_row(conn, account_id, bounty_id)
        reward = _reward(row)
        if existing is not None:
            return {
                "bounty_id": bounty_id,
                "claimed": True,
                "duplicate": True,
                "claimed_at": existing["claimed_at"],
                "reward": {"bits": existing["reward_bits"], "xp": existing["reward_xp"]},
                "receipt": _claim_receipt(conn, existing),
                "wallet": wallet_payload(conn, account_id),
            }

        if not _requirements_met(conn, account_id, row, current):
            raise BountyNotEligible("Bounty requirements are not met yet.")

        receipt = credit(
            conn,
            account_id,
            reward["bits"],
            "bounty.daily",
            f"bounty:{bounty_id}:{account_id}",
        )
        claimed_at = utc_now_iso()
        conn.execute(
            """
            INSERT INTO bounty_claims (
                account_id, bounty_id, claimed_at, ledger_id,
                reward_bits, reward_xp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                bounty_id,
                claimed_at,
                receipt["id"],
                reward["bits"],
                reward["xp"],
            ),
        )
        if reward["xp"]:
            conn.execute(
                "UPDATE pets SET xp = xp + ? WHERE account_id = ?",
                (reward["xp"], account_id),
            )
        return {
            "bounty_id": bounty_id,
            "claimed": True,
            "duplicate": False,
            "claimed_at": claimed_at,
            "reward": reward,
            "receipt": receipt,
            "wallet": wallet_payload(conn, account_id),
        }
