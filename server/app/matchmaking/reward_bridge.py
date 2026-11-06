"""Idempotent match reward receipts with an optional economy adapter."""

from __future__ import annotations

import importlib
import inspect
import sqlite3
import uuid
from typing import Any

from ..db import utc_now_iso

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
    return {
        "id": entitlement_id,
        "match_id": match_id,
        "account_id": award["account_id"],
        "kind": award["kind"],
        "amount": int(award["amount"]),
        "reason": award["reason"],
        "awarded_at": awarded_at,
    }


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


def award_match_rewards(
    conn: sqlite3.Connection,
    match_id: str,
    awards: list[dict[str, Any]],
    awarded_at: str | None = None,
) -> list[dict[str, Any]]:
    timestamp = awarded_at or utc_now_iso()
    economy = load_economy()
    receipts: list[dict[str, Any]] = []
    for award in awards:
        receipt = _record_entitlement(conn, match_id, award, timestamp)
        if receipt is None:
            continue
        receipts.append(receipt)
        credited_with_economy = (
            _call_economy(conn, receipt) if economy is not None else False
        )
        if not credited_with_economy and economy is not None:
            _direct_credit(conn, receipt)
    return receipts
