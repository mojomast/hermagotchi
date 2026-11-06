"""Idempotent match reward receipts with an optional economy adapter."""

from __future__ import annotations

import importlib
import inspect
import sqlite3
import uuid
from typing import Any

from ..db import utc_now_iso
from ..economy.ledger import (
    PRACTICE_DAILY_REWARD_LIMIT,
    PRACTICE_WEEKLY_BITS_LIMIT,
    PVP_DAILY_REWARD_LIMIT,
    PVP_OPPONENT_DAILY_REWARD_LIMIT,
    count_practice_rewards_today,
    count_pvp_opponent_rewarded_today,
    count_pvp_rewarded_today,
    practice_bits_this_week,
    write_transaction,
)

PRACTICE_DAILY_CAP = "practice.daily_cap"
PRACTICE_WEEKLY_CAP = "practice.weekly_cap"
PVP_DAILY_CAP = "pvp.daily_cap"
PVP_OPPONENT_DAILY_CAP = "pvp.opponent_daily_cap"

_ECONOMY_MODULES = (
    "server.app.economy",
    "server.app.economy.service",
    "server.app.economy.rewards",
    "server.app.economy.ledger",
)
_REWARD_FUNCTIONS = (
    "award_match_rewards",
    "grant_match_rewards",
    "credit_match_rewards",
    "credit_reward",
    "award_reward",
    "grant_reward",
    "apply_reward",
    "apply_entitlement",
    "credit",
    "award",
    "grant",
)
_KIND_FUNCTIONS = {
    "bits": ("credit_bits", "award_bits", "grant_bits"),
    "xp": ("credit_xp", "award_xp", "grant_xp"),
}


def load_economy() -> Any | None:
    for name in _ECONOMY_MODULES:
        try:
            module = importlib.import_module(name)
        except Exception:
            continue
        names = _REWARD_FUNCTIONS + tuple(
            name for group in _KIND_FUNCTIONS.values() for name in group
        )
        if any(callable(getattr(module, attr, None)) for attr in names):
            return module
    return None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _record_entitlement(
    conn: sqlite3.Connection,
    match_id: str,
    award: dict[str, Any],
    awarded_at: str,
) -> dict[str, Any] | None:
    entitlement_id = str(uuid.uuid4())
    columns = _columns(conn, "reward_entitlements")
    if "amount" in columns:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO reward_entitlements (
                id, match_id, account_id, kind, amount, awarded_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entitlement_id,
                match_id,
                award["account_id"],
                award["kind"],
                int(award["amount"]),
                awarded_at,
            ),
        )
    else:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO reward_entitlements (
                id, match_id, account_id, kind, awarded_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (entitlement_id, match_id, award["account_id"], award["kind"], awarded_at),
        )
    if cursor.rowcount != 1:
        return None
    receipt = {
        "id": entitlement_id,
        "match_id": match_id,
        "account_id": award["account_id"],
        "kind": award["kind"],
        "amount": int(award["amount"]),
        "reason": award["reason"],
        "awarded_at": awarded_at,
        "reward_status": award.get("reward_status", "paid"),
    }
    if award.get("reward_reason"):
        receipt["reward_reason"] = award["reward_reason"]
    return receipt


def _call_economy(
    conn: sqlite3.Connection,
    receipt: dict[str, Any],
) -> bool:
    economy = load_economy()
    if economy is None:
        return False

    source_event_id = f"match:{receipt['match_id']}:{receipt['account_id']}:{receipt['kind']}"
    context = {
        "conn": conn,
        "db": conn,
        "connection": conn,
        "account_id": receipt["account_id"],
        "amount": receipt["amount"],
        "delta": receipt["amount"],
        "value": receipt["amount"],
        "bits": receipt["amount"] if receipt["kind"] == "bits" else 0,
        "xp": receipt["amount"] if receipt["kind"] == "xp" else 0,
        "kind": receipt["kind"],
        "currency": receipt["kind"],
        "reason": receipt["reason"],
        "source_event_id": source_event_id,
        "source_event": source_event_id,
        "match_id": receipt["match_id"],
        "entitlement_id": receipt["id"],
        "awarded_at": receipt["awarded_at"],
    }

    for module_name in _ECONOMY_MODULES:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        candidate_functions = _KIND_FUNCTIONS.get(
            receipt["kind"], ()
        ) + _REWARD_FUNCTIONS
        for function_name in candidate_functions:
            function = getattr(module, function_name, None)
            if not callable(function):
                continue
            try:
                signature = inspect.signature(function)
            except (TypeError, ValueError):
                continue
            if (
                receipt["kind"] == "xp"
                and function_name in {"credit", "award", "grant"}
                and not {"kind", "currency", "xp"} & set(signature.parameters)
            ):
                continue
            args: list[Any] = []
            kwargs: dict[str, Any] = {}
            supported = True
            for parameter in signature.parameters.values():
                if parameter.kind is inspect.Parameter.VAR_KEYWORD:
                    kwargs.update(context)
                    continue
                if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
                    continue
                value = context.get(parameter.name)
                if value is None and parameter.default is inspect.Parameter.empty:
                    supported = False
                    break
                if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
                    args.append(value)
                else:
                    kwargs[parameter.name] = value
            if not supported:
                continue
            try:
                signature.bind(*args, **kwargs)
            except TypeError:
                continue
            function(*args, **kwargs)
            return True
    return False


def _direct_credit(
    conn: sqlite3.Connection,
    receipt: dict[str, Any],
) -> None:
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if receipt["kind"] == "bits" and {"wallets", "ledger"} <= tables:
        source_event_id = (
            f"match:{receipt['match_id']}:{receipt['account_id']}:{receipt['kind']}"
        )
        if conn.execute(
            "SELECT 1 FROM ledger WHERE source_event_id = ?", (source_event_id,)
        ).fetchone():
            return
        row = conn.execute(
            "SELECT balance, revision FROM wallets WHERE account_id = ?",
            (receipt["account_id"],),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO wallets (account_id, balance, revision) VALUES (?, ?, 1)",
                (receipt["account_id"], receipt["amount"]),
            )
        else:
            conn.execute(
                "UPDATE wallets SET balance = ?, revision = ? WHERE account_id = ?",
                (
                    row["balance"] + receipt["amount"],
                    row["revision"] + 1,
                    receipt["account_id"],
                ),
            )
        conn.execute(
            """
            INSERT INTO ledger (
                id, account_id, delta, reason, source_event_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                receipt["account_id"],
                receipt["amount"],
                receipt["reason"],
                source_event_id,
                receipt["awarded_at"],
            ),
        )
    elif receipt["kind"] == "xp" and "pets" in tables:
        pet_columns = _columns(conn, "pets")
        if "xp" in pet_columns:
            conn.execute(
                "UPDATE pets SET xp = xp + ? WHERE account_id = ?",
                (receipt["amount"], receipt["account_id"]),
            )


def _award_mode(award: dict[str, Any]) -> str | None:
    mode = award.get("mode")
    if mode in {"practice", "casual", "ranked"}:
        return mode
    reason = str(award.get("reason") or "")
    if reason.startswith("battle.practice."):
        return "practice"
    if reason.startswith("battle.casual."):
        return "casual"
    if reason.startswith("battle.ranked."):
        return "ranked"
    return None


def _caps_for_awards(
    conn: sqlite3.Connection,
    awards: list[dict[str, Any]],
    timestamp: str,
) -> dict[str, str]:
    """Return ``{account_id: cap_reason}`` for accounts whose Bits are capped."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for award in awards:
        grouped.setdefault(award["account_id"], []).append(award)

    caps: dict[str, str] = {}
    for account_id, group in grouped.items():
        bits_award = next(
            (award for award in group if award.get("kind") == "bits"), None
        )
        if bits_award is None:
            continue
        amount = int(bits_award.get("amount") or 0)
        mode = _award_mode(bits_award)
        if mode == "practice":
            weekly = practice_bits_this_week(conn, account_id, timestamp)
            daily = count_practice_rewards_today(conn, account_id, timestamp)
            if (
                weekly >= PRACTICE_WEEKLY_BITS_LIMIT
                or weekly + amount > PRACTICE_WEEKLY_BITS_LIMIT
            ):
                caps[account_id] = PRACTICE_WEEKLY_CAP
            elif daily >= PRACTICE_DAILY_REWARD_LIMIT:
                caps[account_id] = PRACTICE_DAILY_CAP
        elif mode in {"casual", "ranked"}:
            if count_pvp_rewarded_today(conn, account_id, timestamp) >= PVP_DAILY_REWARD_LIMIT:
                caps[account_id] = PVP_DAILY_CAP
            else:
                opponent_id = bits_award.get("opponent_id")
                if (
                    isinstance(opponent_id, str)
                    and opponent_id
                    and count_pvp_opponent_rewarded_today(
                        conn, account_id, opponent_id, timestamp
                    )
                    >= PVP_OPPONENT_DAILY_REWARD_LIMIT
                ):
                    caps[account_id] = PVP_OPPONENT_DAILY_CAP
    return caps


def _record_cap_marker(
    conn: sqlite3.Connection,
    match_id: str,
    receipt: dict[str, Any],
    awarded_at: str,
) -> None:
    """Persist a zero-delta ledger marker so match reads can surface the cap."""
    source_event_id = f"match:{match_id}:{receipt['account_id']}:bits"
    existing = conn.execute(
        "SELECT 1 FROM ledger WHERE source_event_id = ?", (source_event_id,)
    ).fetchone()
    if existing is not None:
        return
    conn.execute(
        "INSERT OR IGNORE INTO wallets (account_id, balance, revision) VALUES (?, 0, 0)",
        (receipt["account_id"],),
    )
    wallet = conn.execute(
        "SELECT balance FROM wallets WHERE account_id = ?",
        (receipt["account_id"],),
    ).fetchone()
    conn.execute(
        """
        INSERT INTO ledger (
            id, account_id, delta, reason, source_event_id,
            balance_after, created_at
        ) VALUES (?, ?, 0, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            receipt["account_id"],
            receipt["reward_reason"],
            source_event_id,
            int(wallet["balance"]) if wallet is not None else 0,
            awarded_at,
        ),
    )


def award_match_rewards(
    conn: sqlite3.Connection,
    match_id: str,
    awards: list[dict[str, Any]],
    awarded_at: str | None = None,
) -> list[dict[str, Any]]:
    timestamp = awarded_at or utc_now_iso()
    economy = load_economy()
    receipts: list[dict[str, Any]] = []

    # The cap decision and the credits share one write lock so concurrent
    # workers cannot both consume the last allowance.
    with write_transaction(conn):
        caps = _caps_for_awards(conn, awards, timestamp)
        for award in awards:
            resolved = dict(award)
            cap_reason = caps.get(award["account_id"])
            if cap_reason:
                resolved["amount"] = 0
                resolved["reward_status"] = "capped"
                resolved["reward_reason"] = cap_reason
            else:
                resolved.setdefault("reward_status", "paid")

            receipt = _record_entitlement(conn, match_id, resolved, timestamp)
            if receipt is None:
                continue
            receipts.append(receipt)

            if int(receipt["amount"]) <= 0:
                if receipt.get("reward_reason") and receipt["kind"] == "bits":
                    _record_cap_marker(conn, match_id, receipt, timestamp)
                continue

            credited_with_economy = (
                _call_economy(conn, receipt) if economy is not None else False
            )
            if not credited_with_economy and economy is not None:
                _direct_credit(conn, receipt)
            if receipt["kind"] == "bits":
                conn.execute(
                    "UPDATE ledger SET created_at = ? WHERE source_event_id = ?",
                    (
                        timestamp,
                        f"match:{receipt['match_id']}:{receipt['account_id']}:bits",
                    ),
                )
    return receipts
