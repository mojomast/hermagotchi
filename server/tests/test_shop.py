"""Shop catalog, purchase and equip tests (HGT-W2-G).

Every request uses the in-process FastAPI TestClient; the concurrency test uses
direct service calls with one SQLite connection per worker. No network access.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from server.app.db import connect

RARITY_PRICE = {
    "common": 150,
    "uncommon": 350,
    "rare": 700,
    "epic": 1200,
    "legendary": 2000,
}

CROWN = "hat.binary_crown"
WIZARD_HAT = "hat.wizard_hat"
VISOR = "face.scan_visor"
CAPE = "back.circuit_cape"
AURA = "aura.spark_aura"
EMOTE = "emote.sparkle"


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
    conn = connect(app.state.db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _buy(client, headers, item_id, key):
    return client.post(
        "/v1/shop/purchases",
        headers=headers,
        json={"item_id": item_id, "idempotency_key": key},
    )


def _equip(client, headers, pet_id, item_id, key, slot=None):
    body = {"item_id": item_id, "idempotency_key": key}
    if slot is not None:
        body["slot"] = slot
    return client.post(f"/v1/pets/{pet_id}/equip", headers=headers, json=body)


def test_catalog_lists_seeded_items_with_contract_shape(
    client, auth_headers_a, validate_contract
):
    response = client.get("/v1/catalog", headers=auth_headers_a)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contracts_version"] == "contracts-v1"
    assert body["catalog_version"] == "launch-003"
    assert len(body["items"]) >= 5

    ids = {item["id"] for item in body["items"]}
    assert CROWN in ids

    slots = {item["slot"] for item in body["items"]}
    assert {"head", "face", "back", "aura", "emote"} <= slots

    for item in body["items"]:
        validate_contract("Item", item)
        assert item["active"] is True
        assert item["price_bits"] == RARITY_PRICE[item["rarity"]]
        assert "small_front_v1" in item["compatible_rigs"]


def test_catalog_requires_authentication(client):
    response = client.get("/v1/catalog")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_purchase_requires_idempotency_key(client, auth_headers_a):
    response = client.post(
        "/v1/shop/purchases", headers=auth_headers_a, json={"item_id": EMOTE}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "idempotency_key_required"


def test_purchase_debits_once_and_grants_inventory(
    app, client, auth_headers_a, account_a, validate_contract
):
    _credit(app, account_a, 500, "seed:purchase")

    response = _buy(client, auth_headers_a, EMOTE, "buy-emote-1")

    assert response.status_code == 201, response.text
    body = response.json()
    validate_contract("Item", body["item"])
    validate_contract("LedgerEntry", body["receipt"])
    validate_contract("Wallet", body["wallet"])
    assert body["duplicate"] is False
    assert body["item"]["id"] == EMOTE
    assert body["receipt"]["delta"] == -150
    assert body["wallet"]["balance"] == 350

    ledger = _rows(
        app,
        "SELECT * FROM ledger WHERE account_id = ? AND reason = 'shop.purchase'",
        (account_a,),
    )
    inventory = _rows(app, "SELECT * FROM inventory WHERE account_id = ?", (account_a,))
    assert len(ledger) == 1
    assert len(inventory) == 1
    assert inventory[0]["item_id"] == EMOTE


def test_purchase_is_idempotent_for_same_key(
    app, client, auth_headers_a, account_a
):
    _credit(app, account_a, 500, "seed:idempotent")

    first = _buy(client, auth_headers_a, EMOTE, "same-key")
    second = _buy(client, auth_headers_a, EMOTE, "same-key")

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["duplicate"] is True
    assert second.json()["receipt"]["id"] == first.json()["receipt"]["id"]
    assert second.json()["wallet"]["balance"] == 350
    assert len(_rows(app, "SELECT id FROM ledger WHERE account_id = ?", (account_a,))) == 2
    assert len(_rows(app, "SELECT * FROM inventory WHERE account_id = ?", (account_a,))) == 1


def test_purchase_rejects_insufficient_bits(
    app, client, auth_headers_a, account_a
):
    _credit(app, account_a, 100, "seed:poor")

    response = _buy(client, auth_headers_a, EMOTE, "poor-key")

    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_funds"
    wallet = _rows(
        app, "SELECT balance FROM wallets WHERE account_id = ?", (account_a,)
    )
    assert wallet[0]["balance"] == 100
    assert _rows(app, "SELECT * FROM inventory WHERE account_id = ?", (account_a,)) == []
    assert (
        _rows(
            app,
            "SELECT * FROM ledger WHERE account_id = ? AND reason = 'shop.purchase'",
            (account_a,),
        )
        == []
    )


def test_purchase_rejects_already_owned_item_with_new_key(
    app, client, auth_headers_a, account_a
):
    _credit(app, account_a, 500, "seed:duplicate")

    first = _buy(client, auth_headers_a, EMOTE, "owned-1")
    second = _buy(client, auth_headers_a, EMOTE, "owned-2")

    assert first.status_code == 201, first.text
    assert second.status_code == 409
    assert second.json()["code"] == "item_already_owned"
    assert len(_rows(app, "SELECT * FROM inventory WHERE account_id = ?", (account_a,))) == 1
    purchases = _rows(
        app,
        "SELECT * FROM ledger WHERE account_id = ? AND reason = 'shop.purchase'",
        (account_a,),
    )
    assert len(purchases) == 1


def test_purchase_rejects_idempotency_key_reused_for_another_item(
    app, client, auth_headers_a, account_a
):
    _credit(app, account_a, 500, "seed:reuse")

    first = _buy(client, auth_headers_a, EMOTE, "reused-key")
    second = _buy(client, auth_headers_a, VISOR, "reused-key")

    assert first.status_code == 201, first.text
    assert second.status_code == 409
    assert second.json()["code"] == "idempotency_conflict"
    assert len(_rows(app, "SELECT * FROM inventory WHERE account_id = ?", (account_a,))) == 1


def test_purchase_unknown_item_is_not_found(
    app, client, auth_headers_a, account_a
):
    _credit(app, account_a, 500, "seed:unknown")

    response = _buy(client, auth_headers_a, "hat.does_not_exist", "unknown-key")

    assert response.status_code == 404
    assert response.json()["code"] == "item_not_found"


def test_concurrent_identical_purchase_debits_and_grants_once(
    app, account_a
):
    from server.app.shop import purchase_item

    _credit(app, account_a, 1000, "seed:concurrent")

    def attempt(_index: int):
        conn = connect(app.state.db_path)
        try:
            return purchase_item(conn, account_a, WIZARD_HAT, "concurrent-key")
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(32)))

    assert {result["receipt"]["id"] for result in results} == {
        results[0]["receipt"]["id"]
    }
    assert sum(1 for result in results if result["duplicate"]) == 31

    ledger = _rows(
        app,
        "SELECT * FROM ledger WHERE account_id = ? AND reason = 'shop.purchase'",
        (account_a,),
    )
    inventory = _rows(app, "SELECT * FROM inventory WHERE account_id = ?", (account_a,))
    wallet = _rows(
        app, "SELECT balance FROM wallets WHERE account_id = ?", (account_a,)
    )
    assert len(ledger) == 1
    assert len(inventory) == 1
    assert wallet[0]["balance"] == 1000 - 700

    total = _rows(
        app,
        "SELECT COALESCE(SUM(delta), 0) AS total FROM ledger WHERE account_id = ?",
        (account_a,),
    )
    assert wallet[0]["balance"] == total[0]["total"]


def test_equip_requires_ownership(client, auth_headers_a):
    pet = _adopt(client, auth_headers_a)

    response = _equip(client, auth_headers_a, pet["id"], CROWN, "equip-unowned")

    assert response.status_code == 403
    assert response.json()["code"] == "item_not_owned"


def test_equip_requires_idempotency_key(client, auth_headers_a):
    pet = _adopt(client, auth_headers_a)

    response = client.post(
        f"/v1/pets/{pet['id']}/equip",
        headers=auth_headers_a,
        json={"item_id": CROWN},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "idempotency_key_required"


def test_equip_places_owned_item_in_its_slot(
    app, client, auth_headers_a, account_a, validate_contract
):
    pet = _adopt(client, auth_headers_a)
    _credit(app, account_a, 2500, "seed:equip")
    _buy(client, auth_headers_a, CROWN, "equip-buy")

    response = _equip(client, auth_headers_a, pet["id"], CROWN, "equip-once")

    assert response.status_code == 200, response.text
    body = response.json()
    validate_contract("Item", body["item"])
    assert body["duplicate"] is False
    assert body["pet_id"] == pet["id"]
    assert body["slot"] == "head"
    assert body["equipped_item_id"] == CROWN
    assert body["loadout"]["head"]["id"] == CROWN

    repeat = _equip(client, auth_headers_a, pet["id"], CROWN, "equip-once")
    assert repeat.status_code == 200, repeat.text
    assert repeat.json()["duplicate"] is True
    equipment = _rows(
        app, "SELECT * FROM equipment WHERE pet_id = ?", (pet["id"],)
    )
    assert len(equipment) == 1
    assert equipment[0]["slot"] == "head"
    assert equipment[0]["item_id"] == CROWN


def test_equip_rejects_slot_mismatch(
    app, client, auth_headers_a, account_a
):
    pet = _adopt(client, auth_headers_a)
    _credit(app, account_a, 500, "seed:slot")
    _buy(client, auth_headers_a, EMOTE, "slot-buy")

    response = _equip(
        client, auth_headers_a, pet["id"], EMOTE, "slot-mismatch", slot="head"
    )

    assert response.status_code == 409
    assert response.json()["code"] == "slot_incompatible"


def test_equip_rejects_incompatible_rig(
    app, client, auth_headers_a, account_a
):
    pet = _adopt(client, auth_headers_a)
    conn = connect(app.state.db_path)
    try:
        conn.execute(
            """
            INSERT INTO items (
                id, name, slot, rarity, price_bits, asset_id,
                compatible_rigs_json, catalog_version, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                "head.wrong_rig",
                "Wrong Rig Hat",
                "head",
                "common",
                150,
                "head.wrong_rig",
                json.dumps(["other_rig_v2"]),
                "launch-003",
            ),
        )
        conn.execute(
            """
            INSERT INTO inventory (
                account_id, item_id, acquired_at, source_event_id
            ) VALUES (?, ?, '2026-01-01T00:00:00.000Z', 'test:grant:wrong-rig')
            """,
            (account_a, "head.wrong_rig"),
        )
        conn.commit()
    finally:
        conn.close()

    response = _equip(client, auth_headers_a, pet["id"], "head.wrong_rig", "rig-key")

    assert response.status_code == 409
    assert response.json()["code"] == "item_incompatible"


def test_equip_requires_pet_ownership(
    client, auth_headers_a, auth_headers_b, account_a
):
    from server.app.db import seed_account
    from server.app.economy import credit

    pet = _adopt(client, auth_headers_a)
    conn = connect(_db_path(client))
    try:
        seed_account(conn, "00000000-0000-4000-8000-0000000000b2")
        credit(conn, "00000000-0000-4000-8000-0000000000b2", 2500, "test.grant", "seed:other")
    finally:
        conn.close()
    bought = _buy(client, auth_headers_b, CROWN, "other-buy")
    assert bought.status_code == 201, bought.text

    response = _equip(client, auth_headers_b, pet["id"], CROWN, "other-equip")

    assert response.status_code == 403
    assert response.json()["code"] == "pet_not_owned"


def test_equip_replaces_previous_item_in_same_slot(
    app, client, auth_headers_a, account_a
):
    pet = _adopt(client, auth_headers_a)
    _credit(app, account_a, 3000, "seed:replace")
    _buy(client, auth_headers_a, WIZARD_HAT, "replace-1")
    _buy(client, auth_headers_a, CROWN, "replace-2")

    _equip(client, auth_headers_a, pet["id"], WIZARD_HAT, "replace-equip-1")
    response = _equip(client, auth_headers_a, pet["id"], CROWN, "replace-equip-2")

    assert response.status_code == 200, response.text
    equipment = _rows(app, "SELECT * FROM equipment WHERE pet_id = ?", (pet["id"],))
    assert len(equipment) == 1
    assert equipment[0]["slot"] == "head"
    assert equipment[0]["item_id"] == CROWN
    assert response.json()["loadout"]["head"]["id"] == CROWN


def _db_path(client) -> str:
    return client.app.state.db_path
