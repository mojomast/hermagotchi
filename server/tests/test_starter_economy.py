"""Starter Bits and practice reward tests (HGT-W11-A).

All requests use the in-process FastAPI ``TestClient`` against a temporary
SQLite database. No network access is performed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from server.app.combat import BATTLE_2_VERSION
from server.app.db import connect, migrate

REPO_ROOT = Path(__file__).resolve().parents[2]
STARTER_BITS = 300
STARTER_REASON = "economy.starter_grant"
MIGRATION_VERSION = "0011_starter_and_rate_limits"

TACTIC = {
    "ruleset_version": BATTLE_2_VERSION,
    "stance": "balanced",
    "actions": [{"when": {"always": True}, "move": "basic_attack"}],
}


def _adopt(client, headers, **overrides):
    payload = {"species": "byteblob", "name": "Nibbles"}
    payload.update(overrides)
    return client.post("/v1/pets", headers=headers, json=payload)


def _practice(client, headers, pet_id):
    return client.post(
        "/v1/practice",
        headers=headers,
        json={"pet_id": pet_id, "tactics": TACTIC},
    )


def _rows(app, sql, params=()):
    conn = sqlite3.connect(app.state.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_adopt_credits_starter_bits_once(client, auth_headers_a, account_a, app):
    adopted = _adopt(client, auth_headers_a)
    assert adopted.status_code == 201

    wallet = client.get("/v1/wallet", headers=auth_headers_a)
    assert wallet.status_code == 200
    assert wallet.json()["balance"] == STARTER_BITS

    second = _adopt(client, auth_headers_a, species="patchfox", name="Second")
    assert second.status_code == 409

    wallet_again = client.get("/v1/wallet", headers=auth_headers_a)
    assert wallet_again.json()["balance"] == STARTER_BITS

    grants = _rows(
        app,
        "SELECT * FROM ledger WHERE account_id = ? AND reason = ?",
        (account_a, STARTER_REASON),
    )
    assert len(grants) == 1
    assert grants[0]["delta"] == STARTER_BITS
    assert grants[0]["source_event_id"] == f"{STARTER_REASON}:{account_a}"


def test_practice_rewards_at_least_fifty_bits_and_caps_at_three(
    client, auth_headers_a
):
    adopted = _adopt(client, auth_headers_a)
    assert adopted.status_code == 201
    pet_id = adopted.json()["id"]

    first = _practice(client, auth_headers_a, pet_id)
    assert first.status_code == 200, first.text
    rewards = first.json()["rewards"]
    bits = [reward for reward in rewards if reward["kind"] == "bits"]
    assert bits, rewards
    assert bits[0]["amount"] >= 50

    balance = client.get("/v1/wallet", headers=auth_headers_a).json()["balance"]
    assert balance == STARTER_BITS + bits[0]["amount"]

    for _ in range(2):
        rewarded = _practice(client, auth_headers_a, pet_id)
        assert rewarded.status_code == 200
        assert {reward["kind"] for reward in rewarded.json()["rewards"]} == {
            "bits",
            "xp",
        }

    capped = _practice(client, auth_headers_a, pet_id)
    assert capped.status_code == 200
    capped_body = capped.json()
    capped_rewards = capped_body["rewards"]
    assert {reward["kind"] for reward in capped_rewards} == {"bits", "xp"}
    assert {reward["amount"] for reward in capped_rewards} == {0}
    assert {reward["reward_reason"] for reward in capped_rewards} == {
        "practice.daily_cap"
    }
    assert {reward["reward_status"] for reward in capped_rewards} == {"capped"}
    assert capped_body["match"]["reward_reason"] == "practice.daily_cap"


def test_migration_backfills_eligible_accounts_once(app, account_a):
    conn = connect(app.state.db_path)
    try:
        conn.execute(
            "DELETE FROM ledger WHERE account_id = ? AND reason = ?",
            (account_a, STARTER_REASON),
        )
        conn.execute("DELETE FROM wallets WHERE account_id = ?", (account_a,))
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = ?", (MIGRATION_VERSION,)
        )
        conn.commit()

        migrate(conn)

        wallet = conn.execute(
            "SELECT balance FROM wallets WHERE account_id = ?", (account_a,)
        ).fetchone()
        assert wallet is not None
        assert wallet["balance"] == STARTER_BITS

        # Re-applying the migration must not credit a second time.
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = ?", (MIGRATION_VERSION,)
        )
        conn.commit()
        migrate(conn)

        grants = conn.execute(
            "SELECT COUNT(*) AS total FROM ledger WHERE account_id = ? AND reason = ?",
            (account_a, STARTER_REASON),
        ).fetchone()
        assert grants["total"] == 1
    finally:
        conn.close()


def test_economy_docs_document_starter_bits_and_practice_rewards():
    text = (REPO_ROOT / "docs" / "ECONOMY.md").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "starter" in lowered
    assert "practice" in lowered
    assert "300" in text
    assert "50" in text
