"""Economy wallet/ledger and bounty claim tests (HGT-W2-E).

These tests exercise the authoritative Bits economy directly and through the
HTTP API.  They deliberately avoid network access: every request uses the
in-process FastAPI TestClient from ``conftest.py``.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from server.app.db import connect


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@pytest.fixture
def seeded_bounties(app):
    """Seed three active daily bounties (one claim each)."""
    now = datetime.now(timezone.utc)
    starts_at = _iso(now - timedelta(hours=1))
    expires_at = _iso(now + timedelta(days=1))
    ids = [
        "bounty-daily-001",
        "bounty-daily-002",
        "bounty-daily-003",
    ]
    conn = connect(app.state.db_path)
    try:
        for index, bounty_id in enumerate(ids):
            conn.execute(
                """
                INSERT INTO bounties (
                    id, title, description, starts_at, expires_at,
                    rule_json, reward_json, max_claims, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)
                """,
                (
                    bounty_id,
                    f"Daily bounty {index + 1}",
                    "A server-seeded daily objective.",
                    starts_at,
                    expires_at,
                    json.dumps({"type": "always"}),
                    json.dumps({"bits": 100 + index * 25, "xp": 20 + index * 5}),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return ids


def _wallet(conn: sqlite3.Connection, account_id: str) -> sqlite3.Row:
    return conn.execute("SELECT * FROM wallets WHERE account_id = ?", (account_id,)).fetchone()


def _ledger_rows(conn: sqlite3.Connection, account_id: str):
    return conn.execute(
        "SELECT * FROM ledger WHERE account_id = ? ORDER BY created_at, id",
        (account_id,),
    ).fetchall()


def _assert_invariant(conn: sqlite3.Connection, account_id: str) -> None:
    wallet = _wallet(conn, account_id)
    total = conn.execute(
        "SELECT COALESCE(SUM(delta), 0) AS total FROM ledger WHERE account_id = ?",
        (account_id,),
    ).fetchone()["total"]
    assert wallet is not None
    assert wallet["balance"] == total
    assert wallet["balance"] >= 0


def test_wallet_starts_at_zero(client, auth_headers_a, account_a, validate_contract):
    response = client.get("/v1/wallet", headers=auth_headers_a)

    assert response.status_code == 200
    body = response.json()
    validate_contract("Wallet", body)
    assert body["account_id"] == account_a
    assert body["currency"] == "bits"
    assert body["balance"] == 0
    assert body["revision"] == 0


def test_wallet_requires_authentication(client):
    response = client.get("/v1/wallet")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_credit_updates_wallet_and_appends_ledger(app, account_a, validate_contract):
    from server.app.economy import credit

    conn = connect(app.state.db_path)
    try:
        receipt = credit(conn, account_a, 250, "test.reward", "test:credit:1")
        validate_contract("LedgerEntry", receipt)
        assert receipt["delta"] == 250
        assert receipt["balance_after"] == 250

        second = credit(conn, account_a, 50, "test.reward", "test:credit:2")
        assert second["balance_after"] == 300

        wallet = _wallet(conn, account_a)
        assert wallet["balance"] == 300
        assert wallet["revision"] == 2
        assert len(_ledger_rows(conn, account_a)) == 2
        _assert_invariant(conn, account_a)
    finally:
        conn.close()


def test_credit_is_idempotent_for_same_source_event(app, account_a):
    from server.app.economy import credit

    conn = connect(app.state.db_path)
    try:
        first = credit(conn, account_a, 200, "battle.win", "match:abc:win")
        second = credit(conn, account_a, 200, "battle.win", "match:abc:win")

        assert second == first
        assert len(_ledger_rows(conn, account_a)) == 1
        assert _wallet(conn, account_a)["balance"] == 200
        assert _wallet(conn, account_a)["revision"] == 1
        _assert_invariant(conn, account_a)
    finally:
        conn.close()


def test_100_identical_credit_retries_create_one_ledger_row(app, account_a):
    from server.app.economy import credit

    def attempt(_index: int):
        conn = connect(app.state.db_path)
        try:
            return credit(conn, account_a, 125, "bounty.daily", "bounty:concurrent:1")
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=16) as pool:
        receipts = list(pool.map(attempt, range(100)))

    assert len({receipt["id"] for receipt in receipts}) == 1
    conn = connect(app.state.db_path)
    try:
        rows = _ledger_rows(conn, account_a)
        assert len(rows) == 1
        assert rows[0]["source_event_id"] == "bounty:concurrent:1"
        assert _wallet(conn, account_a)["balance"] == 125
        assert _wallet(conn, account_a)["revision"] == 1
        _assert_invariant(conn, account_a)
    finally:
        conn.close()


def test_debit_updates_balance_and_never_goes_negative(app, account_a):
    from server.app.economy import InsufficientFunds, debit

    conn = connect(app.state.db_path)
    try:
        from server.app.economy import credit

        credit(conn, account_a, 100, "test.reward", "test:debit:fund")
        receipt = debit(conn, account_a, 40, "shop.purchase", "test:debit:1")

        assert receipt["delta"] == -40
        assert receipt["balance_after"] == 60
        assert _wallet(conn, account_a)["balance"] == 60

        with pytest.raises(InsufficientFunds):
            debit(conn, account_a, 61, "shop.purchase", "test:debit:2")

        assert _wallet(conn, account_a)["balance"] == 60
        assert len(_ledger_rows(conn, account_a)) == 2
        _assert_invariant(conn, account_a)
    finally:
        conn.close()


def test_debit_is_idempotent_for_same_source_event(app, account_a):
    from server.app.economy import credit, debit

    conn = connect(app.state.db_path)
    try:
        credit(conn, account_a, 500, "test.reward", "test:debit:idem:fund")
        first = debit(conn, account_a, 150, "shop.purchase", "test:debit:idem")
        second = debit(conn, account_a, 150, "shop.purchase", "test:debit:idem")

        assert second == first
        assert _wallet(conn, account_a)["balance"] == 350
        assert len(_ledger_rows(conn, account_a)) == 2
        _assert_invariant(conn, account_a)
    finally:
        conn.close()


def test_mixed_operations_keep_wallet_equal_to_ledger_sum(app, account_a):
    from server.app.economy import credit, debit

    conn = connect(app.state.db_path)
    try:
        credit(conn, account_a, 800, "battle.win", "mix:1")
        debit(conn, account_a, 150, "shop.purchase", "mix:2")
        credit(conn, account_a, 20, "battle.loss", "mix:3")
        debit(conn, account_a, 650, "shop.purchase", "mix:4")

        assert _wallet(conn, account_a)["balance"] == 800 - 150 + 20 - 650
        _assert_invariant(conn, account_a)
    finally:
        conn.close()


def test_grant_entitlement_credits_bits_and_xp_once(app, client, auth_headers_a, account_a):
    from server.app.economy import grant_entitlement

    adopted = client.post(
        "/v1/pets", headers=auth_headers_a, json={"species": "byteblob", "name": "Bit"}
    )
    assert adopted.status_code == 201
    pet_id = adopted.json()["id"]
    match_id = str(uuid.uuid4())

    conn = connect(app.state.db_path)
    try:
        first = grant_entitlement(conn, match_id, account_a, "win", 80, 50)
        second = grant_entitlement(conn, match_id, account_a, "win", 80, 50)

        assert second == first
        assert first["delta"] == 80
        assert _wallet(conn, account_a)["balance"] == 80
        assert len(_ledger_rows(conn, account_a)) == 1

        entitlement_rows = conn.execute(
            "SELECT * FROM reward_entitlements WHERE match_id = ?", (match_id,)
        ).fetchall()
        assert len(entitlement_rows) == 1
        assert entitlement_rows[0]["kind"] == "win"
        assert entitlement_rows[0]["bits"] == 80
        assert entitlement_rows[0]["xp"] == 50

        pet = client.get(f"/v1/pets/{pet_id}").json()
        assert pet["xp"] == 50
        _assert_invariant(conn, account_a)
    finally:
        conn.close()


def test_get_ledger_is_paginated_newest_first(
    client, auth_headers_a, account_a, app, validate_contract
):
    from server.app.economy import credit

    conn = connect(app.state.db_path)
    try:
        for index in range(5):
            credit(conn, account_a, 10 + index, "test.page", f"page:{index}")
    finally:
        conn.close()

    first = client.get("/v1/ledger?limit=2", headers=auth_headers_a)
    assert first.status_code == 200
    body = first.json()
    assert len(body["entries"]) == 2
    assert body["total"] == 5
    assert body["next_offset"] == 2
    for entry in body["entries"]:
        validate_contract("LedgerEntry", entry)
    assert body["entries"][0]["source_event_id"] == "page:4"

    second = client.get("/v1/ledger?limit=2&offset=2", headers=auth_headers_a)
    assert second.status_code == 200
    assert [entry["source_event_id"] for entry in second.json()["entries"]] == [
        "page:2",
        "page:1",
    ]
    assert second.json()["next_offset"] == 4


def test_ledger_is_scoped_to_the_authenticated_account(
    client, auth_headers_a, auth_headers_b, account_a, app
):
    from server.app.economy import credit

    conn = connect(app.state.db_path)
    try:
        credit(conn, account_a, 75, "test.reward", "scope:1")
    finally:
        conn.close()

    mine = client.get("/v1/ledger", headers=auth_headers_a).json()
    theirs = client.get("/v1/ledger", headers=auth_headers_b).json()
    assert mine["total"] == 1
    assert theirs["total"] == 0
    assert theirs["entries"] == []


def test_get_bounties_lists_seeded_daily_bounties(
    client, auth_headers_a, seeded_bounties
):
    response = client.get("/v1/bounties", headers=auth_headers_a)

    assert response.status_code == 200
    body = response.json()
    assert body["contracts_version"] == "contracts-v1"
    assert [bounty["id"] for bounty in body["bounties"]] == seeded_bounties
    assert all(bounty["claimed"] is False for bounty in body["bounties"])
    assert all(bounty["claimable"] is True for bounty in body["bounties"])
    assert body["bounties"][0]["reward"]["bits"] == 100


def test_claim_bounty_awards_once_and_is_idempotent(
    client, auth_headers_a, account_a, app, seeded_bounties, validate_contract
):
    bounty_id = seeded_bounties[0]

    first = client.post(f"/v1/bounties/{bounty_id}/claim", headers=auth_headers_a)
    assert first.status_code == 200
    body = first.json()
    assert body["bounty_id"] == bounty_id
    assert body["reward"]["bits"] == 100
    assert body["reward"]["xp"] == 20
    validate_contract("Wallet", body["wallet"])
    assert body["wallet"]["balance"] == 100
    assert body["claimed"] is True

    second = client.post(f"/v1/bounties/{bounty_id}/claim", headers=auth_headers_a)
    assert second.status_code == 200
    assert second.json()["receipt"]["id"] == body["receipt"]["id"]
    assert second.json()["wallet"]["balance"] == 100

    conn = connect(app.state.db_path)
    try:
        claims = conn.execute(
            "SELECT * FROM bounty_claims WHERE account_id = ? AND bounty_id = ?",
            (account_a, bounty_id),
        ).fetchall()
        assert len(claims) == 1
        assert len(_ledger_rows(conn, account_a)) == 1
        assert _wallet(conn, account_a)["balance"] == 100
        _assert_invariant(conn, account_a)
    finally:
        conn.close()


def test_claim_bounty_awards_xp_to_pet(
    client, auth_headers_a, account_a, app, seeded_bounties
):
    adopted = client.post(
        "/v1/pets", headers=auth_headers_a, json={"species": "patchfox", "name": "Ember"}
    )
    assert adopted.status_code == 201
    pet_id = adopted.json()["id"]

    claimed = client.post(
        f"/v1/bounties/{seeded_bounties[1]}/claim", headers=auth_headers_a
    )
    assert claimed.status_code == 200
    assert claimed.json()["reward"]["xp"] == 25

    pet = client.get(f"/v1/pets/{pet_id}").json()
    assert pet["xp"] == 25


def test_claim_unknown_bounty_returns_not_found(client, auth_headers_a):
    response = client.post("/v1/bounties/does-not-exist/claim", headers=auth_headers_a)

    assert response.status_code == 404
    assert response.json()["code"] == "bounty_not_found"


def test_claim_expired_bounty_is_rejected(client, auth_headers_a, app):
    now = datetime.now(timezone.utc)
    conn = connect(app.state.db_path)
    try:
        conn.execute(
            """
            INSERT INTO bounties (
                id, title, description, starts_at, expires_at,
                rule_json, reward_json, max_claims, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)
            """,
            (
                "bounty-expired",
                "Expired",
                "No longer active.",
                _iso(now - timedelta(days=3)),
                _iso(now - timedelta(days=2)),
                json.dumps({"type": "always"}),
                json.dumps({"bits": 500, "xp": 50}),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.post("/v1/bounties/bounty-expired/claim", headers=auth_headers_a)

    assert response.status_code == 409
    assert response.json()["code"] == "bounty_not_active"


def test_bounty_claim_requires_authentication(client, seeded_bounties):
    response = client.post(f"/v1/bounties/{seeded_bounties[0]}/claim")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
