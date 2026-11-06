"""Cross-account authorization and client-payload isolation tests (HGT-W6-N).

Every request uses the in-process FastAPI ``TestClient`` and the SQLite test
database from ``conftest.py``. No network access is performed.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from server.app import ECONOMY_VERSION, RULESET_VERSION
from server.app.combat import resolve_match, validate_tactic_card
from server.app.db import connect

FIXTURES = Path(__file__).parent / "fixtures" / "matches"
EMOTE = "emote.sparkle"
CROWN = "hat.binary_crown"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _adopt(client, headers, species="byteblob", name="Bit"):
    response = client.post(
        "/v1/pets", headers=headers, json={"species": species, "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _credit(app, account_id, amount, source_event_id):
    from server.app.economy import credit

    conn = connect(app.state.db_path)
    try:
        return credit(conn, account_id, amount, "test.grant", source_event_id)
    finally:
        conn.close()


def _rows(app, sql, params=()):
    conn = sqlite3.connect(app.state.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _wallet_balance(app, account_id):
    rows = _rows(
        app, "SELECT balance FROM wallets WHERE account_id = ?", (account_id,)
    )
    return rows[0]["balance"] if rows else 0


def _buy(client, headers, item_id, key):
    return client.post(
        "/v1/shop/purchases",
        headers=headers,
        json={"item_id": item_id, "idempotency_key": key},
    )


def test_user_b_cannot_read_a_wallet_or_ledger(
    app, client, auth_headers_a, auth_headers_b, account_a, account_b
):
    _credit(app, account_a, 420, "isolation:wallet:a")

    wallet_b = client.get("/v1/wallet", headers=auth_headers_b)
    ledger_b = client.get("/v1/ledger", headers=auth_headers_b)

    assert wallet_b.status_code == 200
    assert wallet_b.json()["account_id"] == account_b
    assert wallet_b.json()["balance"] == 0
    assert ledger_b.status_code == 200
    assert ledger_b.json()["total"] == 0
    assert ledger_b.json()["entries"] == []

    wallet_a = client.get("/v1/wallet", headers=auth_headers_a).json()
    assert wallet_a["balance"] == 420
    assert ledger_b.json()["account_id"] != account_a


def test_user_b_cannot_mutate_a_pet_or_grant_inventory_to_a(
    app, client, auth_headers_a, auth_headers_b, account_a, account_b
):
    pet_a = _adopt(client, auth_headers_a, "patchfox", "Ash")
    _credit(app, account_b, 30000, "isolation:pet:b")

    bought = _buy(client, auth_headers_b, CROWN, "isolation:buy:b")
    assert bought.status_code == 201, bought.text

    equip = client.post(
        f"/v1/pets/{pet_a['id']}/equip",
        headers=auth_headers_b,
        json={"item_id": CROWN, "idempotency_key": "isolation:equip:b"},
    )

    assert equip.status_code == 403
    assert equip.json()["code"] == "pet_not_owned"
    assert _rows(app, "SELECT * FROM equipment WHERE pet_id = ?", (pet_a["id"],)) == []
    assert (
        len(_rows(app, "SELECT * FROM inventory WHERE account_id = ?", (account_a,)))
        == 0
    )
    assert (
        len(_rows(app, "SELECT * FROM inventory WHERE account_id = ?", (account_b,)))
        == 1
    )


def test_public_pet_view_hides_owner_private_fields_from_user_b(
    client, auth_headers_a, auth_headers_b, account_a
):
    pet_a = _adopt(client, auth_headers_a, "nullgeist", "Wisp")

    response = client.get(f"/v1/pets/{pet_a['id']}", headers=auth_headers_b)

    assert response.status_code == 200
    public = response.json()
    assert public["id"] == pet_a["id"]
    assert "account_id" not in public
    assert "appearance_seed" not in public
    assert "care_updated_at" not in public
    assert account_a not in str(public)


def test_client_account_override_does_not_spend_or_grant_for_another_user(
    app, client, auth_headers_a, auth_headers_b, account_a, account_b
):
    _credit(app, account_b, 500, "isolation:override:b")

    response = client.post(
        "/v1/shop/purchases",
        headers=auth_headers_b,
        json={
            "item_id": EMOTE,
            "idempotency_key": "isolation:override",
            "account_id": account_a,
            "owner_id": account_a,
            "balance": 999999,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["wallet"]["account_id"] == account_b
    assert response.json()["wallet"]["balance"] == 350
    assert _wallet_balance(app, account_a) == 0
    assert _wallet_balance(app, account_b) == 350
    assert (
        _rows(app, "SELECT * FROM inventory WHERE account_id = ?", (account_a,))
        == []
    )
    assert (
        len(_rows(app, "SELECT * FROM inventory WHERE account_id = ?", (account_b,)))
        == 1
    )


def test_invalid_purchase_payload_cannot_mint_bits(
    app, client, auth_headers_a, account_a
):
    response = client.post(
        "/v1/shop/purchases",
        headers=auth_headers_a,
        json={
            "item_id": EMOTE,
            "idempotency_key": "isolation:mint",
            "price_bits": 0,
            "delta": 100000,
            "amount": 100000,
            "balance": 100000,
            "receipt": {"delta": 100000},
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_funds"
    assert _wallet_balance(app, account_a) == 0
    assert _rows(app, "SELECT * FROM ledger WHERE account_id = ?", (account_a,)) == []
    assert (
        _rows(app, "SELECT * FROM inventory WHERE account_id = ?", (account_a,))
        == []
    )


def test_invalid_purchase_item_cannot_be_priced_by_the_client(
    app, client, auth_headers_a, account_a
):
    _credit(app, account_a, 150, "isolation:price:a")

    response = client.post(
        "/v1/shop/purchases",
        headers=auth_headers_a,
        json={
            "item_id": "hat.does_not_exist",
            "idempotency_key": "isolation:price",
            "price_bits": 0,
            "rarity": "common",
        },
    )

    assert response.status_code == 404
    assert response.json()["code"] == "item_not_found"
    assert _wallet_balance(app, account_a) == 150
    assert (
        _rows(
            app,
            "SELECT * FROM ledger WHERE account_id = ? AND reason = 'shop.purchase'",
            (account_a,),
        )
        == []
    )


def test_client_cannot_force_match_outcome_or_rewards(
    app,
    client,
    auth_headers_a,
    auth_headers_b,
    account_a,
    account_b,
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")

    challenge = client.post(
        "/v1/challenges",
        headers=auth_headers_a,
        json={"defender_id": account_b, "mode": "casual"},
    ).json()
    accepted = client.post(
        f"/v1/challenges/{challenge['id']}/respond",
        headers=auth_headers_b,
        json={"action": "accept"},
    )
    assert accepted.status_code == 200, accepted.text
    match_id = accepted.json()["match"]["id"]

    aggressive = _load("tactic_aggressive.json")
    defensive = _load("tactic_defensive.json")
    first = client.post(
        f"/v1/matches/{match_id}/tactics",
        headers=auth_headers_a,
        json={"card": aggressive},
    )
    assert first.status_code == 200, first.text

    forced = client.post(
        f"/v1/matches/{match_id}/tactics",
        headers=auth_headers_b,
        json={
            "card": defensive,
            "winner": "b",
            "result": "win",
            "damage": 9999,
            "rewards": {"bits": 100000},
            "replay_hash": "client-chosen",
            "final_hp": {"a": 0, "b": 100},
        },
    )

    assert forced.status_code == 200, forced.text
    body = forced.json()
    assert body["match"]["status"] == "resolved"
    assert body["match"]["replay_hash"] != "client-chosen"

    expected = resolve_match(
        RULESET_VERSION,
        {"species": "patchfox"},
        {"species": "nullgeist"},
        validate_tactic_card(aggressive),
        validate_tactic_card(defensive),
        body["match"]["seed"],
    )
    assert body["replay"]["replay_hash"] == expected.replay_hash
    assert body["match"]["replay_hash"] == expected.replay_hash
    assert body["replay"]["winner"] == expected.winner
    assert body["replay"]["final_hp"] == expected.final_hp
    assert body["match"]["economy_version"] == ECONOMY_VERSION

    awards = _rows(
        app,
        "SELECT account_id, kind FROM reward_entitlements WHERE match_id = ?",
        (match_id,),
    )
    assert len(awards) == 4
    assert {award["kind"] for award in awards} == {"bits", "xp"}

    ledger_awards = _rows(
        app,
        "SELECT account_id, delta, reason FROM ledger WHERE reason LIKE 'battle.casual.%'",
    )
    assert len(ledger_awards) == 2
    for award in ledger_awards:
        assert award["reason"].endswith(".bits")
        assert award["delta"] in {20, 70, 80, 130}
    # Starter grant (300) plus at most one casual bits award (80/20 or similar).
    assert _wallet_balance(app, account_a) <= 300 + 130
    assert _wallet_balance(app, account_b) <= 300 + 130


def test_tactic_payload_cannot_inject_winner_fields_into_the_engine(
    client, auth_headers_a, auth_headers_b, account_a, account_b
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "byteblob", "Blob")
    challenge = client.post(
        "/v1/challenges",
        headers=auth_headers_a,
        json={"defender_id": account_b, "mode": "casual"},
    ).json()
    match_id = client.post(
        f"/v1/challenges/{challenge['id']}/respond",
        headers=auth_headers_b,
        json={"action": "accept"},
    ).json()["match"]["id"]

    tampered = {
        **_load("tactic_aggressive.json"),
        "winner": "a",
        "damage": 9999,
        "rewards": {"bits": 100000},
    }
    response = client.post(
        f"/v1/matches/{match_id}/tactics",
        headers=auth_headers_a,
        json={"card": tampered},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "tactic_field_unknown"
    match = client.get(f"/v1/matches/{match_id}", headers=auth_headers_a).json()
    assert match["match"]["status"] == "pending"
    assert match["replay"] is None
