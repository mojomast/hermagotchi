"""Economy repricing and mythic prestige tier tests (HGT-W12-A).

The migration is forward-only and SQLite cannot ALTER a CHECK constraint, so
these tests exercise the rebuilt ``items`` table as well as the catalog and
purchase behaviour. Every request runs in-process against a temporary SQLite
database; no network access is used.
"""

from __future__ import annotations

import json
from pathlib import Path

from server.app.db import MIGRATIONS_DIR, connect, init_db
from server.app.shop.catalog import item_payload

MIGRATION_VERSION = "0012_economy_reprice_mythic"

EPIC_PRICES = {
    "aura.spark_aura": 3000,
    "aura.ember_halo": 3200,
    "face.stack_trace": 3400,
    "hat.bloom_filter": 3600,
    "hat.lambda_tiara": 3800,
    "front.usb_sword": 4000,
    "aura.flame_wall": 4200,
    "back.tiny_jetpack": 4400,
    "back.webhook_wings": 4600,
    "aura.starfield": 4800,
    "title.pixel_pilot": 5000,
}

LEGENDARY_PRICES = {
    "face.laser_focus": 12000,
    "back.glider_cloak": 14000,
    "hat.cron_crown": 16000,
    "front.pixel_blade": 18000,
    "aura.rainbow_arc": 22000,
    "hat.binary_crown": 25000,
}

MYTHIC_ITEMS = {
    "aura.mythic_prism": {
        "name": "Mythic Prism",
        "slot": "aura",
        "asset_id": "aura.rainbow_arc",
        "price_bits": 50000,
    },
    "hat.mythic_sovereign": {
        "name": "Mythic Sovereign",
        "slot": "head",
        "asset_id": "hat.binary_crown",
        "price_bits": 52000,
    },
    "back.mythic_parallax": {
        "name": "Mythic Parallax",
        "slot": "back",
        "asset_id": "back.glider_cloak",
        "price_bits": 48000,
    },
    "title.mythic_overclock": {
        "name": "Mythic Overclock",
        "slot": "title",
        "asset_id": "title.pixel_pilot",
        "price_bits": 55000,
    },
}

MYTHIC_PRICES = {
    item_id: details["price_bits"] for item_id, details in MYTHIC_ITEMS.items()
}


def _credit(app, account_id, amount, source_event_id):
    from server.app.economy import credit

    conn = connect(app.state.db_path)
    try:
        return credit(conn, account_id, amount, "test.grant", source_event_id)
    finally:
        conn.close()


def _buy(client, headers, item_id, key):
    return client.post(
        "/v1/shop/purchases",
        headers=headers,
        json={"item_id": item_id, "idempotency_key": key},
    )


def _rows(app, sql, params=()):
    conn = connect(app.state.db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_migration_applies_and_seeds_four_mythics(tmp_path):
    db_path = init_db(tmp_path / "economy-reprice.db")
    conn = connect(db_path)
    try:
        versions = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations")
        }
        assert MIGRATION_VERSION in versions

        mythics = conn.execute(
            "SELECT * FROM items WHERE rarity = 'mythic' ORDER BY id"
        ).fetchall()
        assert {row["id"] for row in mythics} == set(MYTHIC_ITEMS)

        for row in mythics:
            expected = MYTHIC_ITEMS[row["id"]]
            assert row["name"] == expected["name"]
            assert row["slot"] == expected["slot"]
            assert row["asset_id"] == expected["asset_id"]
            assert row["price_bits"] == expected["price_bits"]
            assert json.loads(row["compatible_rigs_json"]) == ["small_front_v1"]
            assert row["catalog_version"] == "launch-003"
            assert row["active"] == 1
    finally:
        conn.close()


def test_migration_sets_exact_epic_and_legendary_prices(tmp_path):
    db_path = init_db(tmp_path / "economy-prices.db")
    conn = connect(db_path)
    try:
        for item_id, price in {**EPIC_PRICES, **LEGENDARY_PRICES}.items():
            row = conn.execute(
                "SELECT price_bits FROM items WHERE id = ?", (item_id,)
            ).fetchone()
            assert row is not None, f"missing item {item_id}"
            assert row["price_bits"] == price

        for item_id, price in {
            "front.pixel_badge": 150,
            "face.scan_visor": 350,
            "hat.wizard_hat": 700,
        }.items():
            row = conn.execute(
                "SELECT price_bits FROM items WHERE id = ?", (item_id,)
            ).fetchone()
            assert row["price_bits"] == price
    finally:
        conn.close()


def test_catalog_lists_four_mythics_at_the_new_prices(
    client, auth_headers_a, validate_contract
):
    response = client.get("/v1/catalog", headers=auth_headers_a)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["catalog_version"] == "launch-003"

    by_id = {item["id"]: item for item in body["items"]}
    for item_id, price in MYTHIC_PRICES.items():
        item = by_id[item_id]
        assert item["rarity"] == "mythic"
        assert item["price_bits"] == price
        assert item["asset_id"] == MYTHIC_ITEMS[item_id]["asset_id"]
        validate_contract("Item", item)

    assert {item["id"] for item in body["items"] if item["rarity"] == "mythic"} == set(
        MYTHIC_ITEMS
    )


def test_mythic_rarity_is_accepted_by_the_rebuilt_table(app, validate_contract):
    payload = {
        "id": "hat.test_mythic",
        "name": "Test Mythic",
        "slot": "head",
        "rarity": "mythic",
        "price_bits": 60000,
        "asset_id": "hat.binary_crown",
        "compatible_rigs": ["small_front_v1"],
        "catalog_version": "launch-003",
        "active": True,
    }
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
                payload["id"],
                payload["name"],
                payload["slot"],
                payload["rarity"],
                payload["price_bits"],
                payload["asset_id"],
                json.dumps(payload["compatible_rigs"]),
                payload["catalog_version"],
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM items WHERE id = ?", (payload["id"],)
        ).fetchone()
    finally:
        conn.close()

    contract_payload = item_payload(row)
    assert contract_payload["rarity"] == "mythic"
    validate_contract("Item", contract_payload)


def test_buying_a_mythic_debits_the_prestige_price(
    app, client, auth_headers_a, account_a, validate_contract
):
    item_id = "aura.mythic_prism"
    price = MYTHIC_PRICES[item_id]
    _credit(app, account_a, price, "seed:mythic")

    response = _buy(client, auth_headers_a, item_id, "buy-mythic-1")

    assert response.status_code == 201, response.text
    body = response.json()
    validate_contract("Item", body["item"])
    assert body["item"]["rarity"] == "mythic"
    assert body["item"]["price_bits"] == price
    assert body["receipt"]["delta"] == -price
    assert body["wallet"]["balance"] == 0

    inventory = _rows(
        app, "SELECT item_id FROM inventory WHERE account_id = ?", (account_a,)
    )
    assert [row["item_id"] for row in inventory] == [item_id]


def test_migration_rebuild_preserves_inventory_equipment_and_indexes(
    app, client, auth_headers_a, account_a
):
    adopted = client.post(
        "/v1/pets",
        headers=auth_headers_a,
        json={"species": "byteblob", "name": "Bit"},
    )
    assert adopted.status_code == 201, adopted.text
    pet_id = adopted.json()["id"]

    _credit(app, account_a, 1000, "seed:rebuild")
    bought = _buy(client, auth_headers_a, "front.pixel_badge", "rebuild-buy")
    assert bought.status_code == 201, bought.text
    equipped = client.post(
        f"/v1/pets/{pet_id}/equip",
        headers=auth_headers_a,
        json={"item_id": "front.pixel_badge", "idempotency_key": "rebuild-equip"},
    )
    assert equipped.status_code == 200, equipped.text

    conn = connect(app.state.db_path)
    try:
        script = (MIGRATIONS_DIR / f"{MIGRATION_VERSION}.sql").read_text(
            encoding="utf-8"
        )
        conn.executescript(script)
        conn.commit()

        inventory = conn.execute(
            "SELECT item_id FROM inventory WHERE account_id = ?", (account_a,)
        ).fetchall()
        equipment = conn.execute(
            "SELECT item_id FROM equipment WHERE pet_id = ?", (pet_id,)
        ).fetchall()
        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'items'"
            )
        }
        inventory_fks = {
            row["table"] for row in conn.execute("PRAGMA foreign_key_list(inventory)")
        }
        equipment_fks = {
            row["table"] for row in conn.execute("PRAGMA foreign_key_list(equipment)")
        }

        assert [row["item_id"] for row in inventory] == ["front.pixel_badge"]
        assert [row["item_id"] for row in equipment] == ["front.pixel_badge"]
        assert "idx_items_slot_active" in indexes
        assert "items" in inventory_fks
        assert "items" in equipment_fks
        assert (
            conn.execute(
                "SELECT COUNT(*) AS total FROM items WHERE rarity = 'mythic'"
            ).fetchone()["total"]
            == 4
        )
    finally:
        conn.close()
