# Shop, inventory and equipment (shop)

The shop is the cosmetic Bits sink for contracts-v1. The server owns catalog
prices, ownership and equipped loadouts; clients never submit a price, balance,
or grant. Appearance items never modify combat stats.

## Catalog

`GET /v1/catalog` returns the active catalog:

```json
{
  "contracts_version": "contracts-v1",
  "catalog_version": "launch-003",
  "items": [
    {
      "contracts_version": "contracts-v1",
      "id": "hat.binary_crown",
      "name": "Binary Crown",
      "slot": "head",
      "rarity": "legendary",
      "price_bits": 25000,
      "asset_id": "hat.binary_crown",
      "compatible_rigs": ["small_front_v1"],
      "catalog_version": "launch-003",
      "active": true
    }
  ]
}
```

Each item validates against `shared/schema/item.schema.json`. Slots are
`head`, `face`, `back`, `front`, `aura`, `emote`, `habitat`, `title`; one item
may be equipped per slot. Only `small_front_v1` is compatible today. The rarity
enum is `common`, `uncommon`, `rare`, `epic`, `legendary`, `mythic`.

## Prices

Migration `0004_shop.sql` and `0008_cosmetics_pack.sql` seed the catalog;
`0009_launch003.sql` advances active rows to `launch-003`; migration
`0012_economy_reprice_mythic.sql` reprices epic and legendary items and inserts
the mythic tier. Common, uncommon and rare stay flat.

| Rarity | Price | Items |
|---|---:|---|
| common | 150 | Flat across the catalog |
| uncommon | 350 | Flat across the catalog |
| rare | 700 | Flat across the catalog |
| epic | 3,000-5,000 | Per-item prices below |
| legendary | 12,000-25,000 | Per-item prices below |
| mythic | 48,000-55,000 | Four prestige items below |

### Epic

| Item | Bits |
|---|---:|
| `aura.spark_aura` | 3,000 |
| `aura.ember_halo` | 3,200 |
| `face.stack_trace` | 3,400 |
| `hat.bloom_filter` | 3,600 |
| `hat.lambda_tiara` | 3,800 |
| `front.usb_sword` | 4,000 |
| `aura.flame_wall` | 4,200 |
| `back.tiny_jetpack` | 4,400 |
| `back.webhook_wings` | 4,600 |
| `aura.starfield` | 4,800 |
| `title.pixel_pilot` | 5,000 |

### Legendary

| Item | Bits |
|---|---:|
| `face.laser_focus` | 12,000 |
| `back.glider_cloak` | 14,000 |
| `hat.cron_crown` | 16,000 |
| `front.pixel_blade` | 18,000 |
| `aura.rainbow_arc` | 22,000 |
| `hat.binary_crown` | 25,000 |

### Mythic

Mythics are prestige variants that reuse existing launch-003 art. They add no
PNG files and do not change `assets/` or the manifest.

| Item | Name | Slot | Asset id | Bits |
|---|---|---|---|---:|
| `aura.mythic_prism` | Mythic Prism | aura | `aura.rainbow_arc` | 50,000 |
| `hat.mythic_sovereign` | Mythic Sovereign | head | `hat.binary_crown` | 52,000 |
| `back.mythic_parallax` | Mythic Parallax | back | `back.glider_cloak` | 48,000 |
| `title.mythic_overclock` | Mythic Overclock | title | `title.pixel_pilot` | 55,000 |

Because a mythic row's `asset_id` points at an existing manifest asset, the
desktop shop resolves the same thumbnail and composed preview those base items
already use. Shop code keys thumbnails by `asset_id` (falling back to item id
only when a catalog row has no asset id), so no new thumbnail files are needed.

The desktop shop renders distinct **Legendary** and **Mythic** badges, keeps
the Owned/Equipped badges, and defaults to price ascending with item id as the
tie-breaker. Rarity styling lives in `desktop/src/ui/styles.css`.

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
  wallet, ledger and inventory untouched. Mythic purchases debit their full
  prestige price (48,000-55,000 Bits).
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

Mythic items are equipped exactly like their base slot items; reuse of an
`asset_id` only affects rendering, not ownership or equipment rules.

## Storage

Migration `0004_shop.sql` adds:

- `items(id, name, slot, rarity, price_bits, asset_id, compatible_rigs_json,
  catalog_version, active)`
- `inventory(account_id, item_id, acquired_at, source_event_id)` with
  `PRIMARY KEY (account_id, item_id)` and unique `source_event_id`
- `equipment(pet_id, slot, item_id, equipped_at)` with
  `PRIMARY KEY (pet_id, slot)`

Migration `0012_economy_reprice_mythic.sql` rebuilds `items` (SQLite cannot
widen a CHECK in place) to add `mythic`, preserves every row, and recreates
`idx_items_slot_active`. `inventory.item_id` and `equipment.item_id` continue to
reference `items`, so existing ownership and loadouts survive the rebuild.
Purchases call only the public `server.app.economy.debit` and wallet helpers;
economy internals and combat/matchmaking are unchanged.

## Tests

```bash
python3 -m pytest -q server/tests/test_shop.py server/tests/test_economy_reprice.py
python3 -m pytest -q tests/test_shop_thumbs.py
```

Coverage includes catalog contract shape and per-item rarity prices,
authentication, required idempotency keys, debit/grant atomicity, insufficient
Bits, duplicate ownership, key reuse conflicts, 32 concurrent identical
purchases producing one debit and one inventory row, equip ownership and pet
ownership, slot and rig compatibility, idempotent re-equip, same-slot
replacement, the rebuilt items table, and the four mythic rows. The thumbnail
pack still contains exactly the 81 manifest assets, with mythics reusing them.
No network is used.
