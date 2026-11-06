# Shop, inventory and equipment (shop)

The shop is the cosmetic Bits sink for contracts-v1. The server owns catalog
prices, ownership and equipped loadouts; clients never submit a price, balance,
or grant. Appearance items never modify combat stats.

## Catalog

`GET /v1/catalog` returns the active catalog:

```json
{
  "contracts_version": "contracts-v1",
  "catalog_version": "launch-001",
  "items": [
    {
      "contracts_version": "contracts-v1",
      "id": "hat.binary_crown",
      "name": "Binary Crown",
      "slot": "head",
      "rarity": "legendary",
      "price_bits": 2000,
      "asset_id": "hat.binary_crown",
      "compatible_rigs": ["small_front_v1"],
      "catalog_version": "launch-001",
      "active": true
    }
  ]
}
```

Each item validates against `shared/schema/item.schema.json`. Slots are
`head`, `face`, `back`, `front`, `aura`, `emote`, `habitat`, `title`; one item
may be equipped per slot. Only `small_front_v1` is compatible today.

Migration `0004_shop.sql` seeds nine items at the frozen rarity prices:

| Rarity | Bits | Seeded items |
|---|---:|---|
| common | 150 | `front.pixel_badge`, `emote.sparkle` |
| uncommon | 350 | `face.scan_visor`, `habitat.glow_moss` |
| rare | 700 | `hat.wizard_hat`, `back.circuit_cape` |
| epic | 1200 | `aura.spark_aura`, `title.pixel_pilot` |
| legendary | 2000 | `hat.binary_crown` |

## Purchase

```
POST /v1/shop/purchases
{
  "item_id": "hat.wizard_hat",
  "idempotency_key": "<uuid-or-ulid>"
}
```

`idempotency_key` is required in the body or the `Idempotency-Key` header.
Success returns `201` with the item, ledger receipt, wallet projection,
`duplicate`, and `acquired_at`:

```json
{
  "contracts_version": "contracts-v1",
  "item": { "...": "Item" },
  "duplicate": false,
  "acquired_at": "2026-11-06T12:00:00.000Z",
  "receipt": { "...": "LedgerEntry" },
  "wallet": { "...": "Wallet" }
}
```

The debit, inventory row and wallet update commit in one `BEGIN IMMEDIATE`
transaction. `inventory.source_event_id` is globally unique and derived from
`(account_id, idempotency_key)`:

- Replaying the same key and item returns the original receipt with
  `duplicate: true`; no second debit or inventory row exists.
- Reusing a key for a different item returns `409 idempotency_conflict`.
- Buying an already-owned item with a new key returns
  `409 item_already_owned`.
- An unaffordable purchase returns `409 insufficient_funds` and leaves the
  wallet, ledger and inventory untouched.
- The wallet invariant `balance == SUM(ledger.delta)` holds after every result.

Concurrent identical requests serialize on SQLite's write lock. Exactly one
request inserts the ledger and inventory rows; the rest observe the receipt
and report `duplicate: true`.

## Equip

```
POST /v1/pets/{pet_id}/equip
{
  "item_id": "hat.wizard_hat",
  "idempotency_key": "<uuid-or-ulid>",
  "slot": "head"
}
```

`idempotency_key` is required. The server verifies that the pet belongs to the
authenticated account, the item exists, is active, is owned by that account,
and is compatible with the pet's rig and requested slot. Success returns the
item, `slot`, `duplicate`, `equipped_at`, and the full `loadout` keyed by slot.

- Unowned item: `403 item_not_owned`.
- Another account's pet: `403 pet_not_owned`.
- Wrong slot: `409 slot_incompatible`.
- Incompatible rig: `409 item_incompatible`.
- Equipping the same item again is idempotent (`duplicate: true`).
- Equipping a different owned item in the same slot replaces the previous one;
  `equipment` has `PRIMARY KEY (pet_id, slot)`.

## Storage

Migration `0004_shop.sql` adds:

- `items(id, name, slot, rarity, price_bits, asset_id, compatible_rigs_json,
  catalog_version, active)`
- `inventory(account_id, item_id, acquired_at, source_event_id)` with
  `PRIMARY KEY (account_id, item_id)` and unique `source_event_id`
- `equipment(pet_id, slot, item_id, equipped_at)` with
  `PRIMARY KEY (pet_id, slot)`

Purchases call only the public `server.app.economy.debit` and wallet helpers;
economy internals and combat/matchmaking are unchanged.

## Tests

```bash
python3 -m pytest -q server/tests/test_shop.py
```

Coverage includes catalog contract shape and rarity prices, authentication,
required idempotency keys, debit/grant atomicity, insufficient Bits, duplicate
ownership, key reuse conflicts, 32 concurrent identical purchases producing one
debit and one inventory row, equip ownership and pet ownership, slot and rig
compatibility, idempotent re-equip, and same-slot replacement. No network is
used.
