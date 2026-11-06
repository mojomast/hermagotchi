-- Economy repricing + mythic prestige tier (HGT-W12-A). Forward-only.
--
-- SQLite cannot ALTER a CHECK constraint, so rebuild items with the expanded
-- rarity allowlist while foreign keys are disabled. inventory.item_id and
-- equipment.item_id reference the table by name, so they keep resolving to the
-- renamed rebuild and no ownership/loadout row is lost. Existing indexes are
-- dropped with the old table and recreated below.

PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS items_reprice_rebuild;
CREATE TABLE items_reprice_rebuild (
    id TEXT PRIMARY KEY
        CHECK (id GLOB '[a-z]*.[a-z0-9_]*' AND length(id) BETWEEN 3 AND 64),
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 48),
    slot TEXT NOT NULL
        CHECK (slot IN ('head', 'face', 'back', 'front', 'aura', 'emote', 'habitat', 'title')),
    rarity TEXT NOT NULL
        CHECK (rarity IN ('common', 'uncommon', 'rare', 'epic', 'legendary', 'mythic')),
    price_bits INTEGER NOT NULL CHECK (price_bits >= 0),
    asset_id TEXT NOT NULL CHECK (length(asset_id) BETWEEN 1 AND 64),
    compatible_rigs_json TEXT NOT NULL,
    catalog_version TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

INSERT INTO items_reprice_rebuild (
    id, name, slot, rarity, price_bits, asset_id,
    compatible_rigs_json, catalog_version, active
)
SELECT
    id, name, slot, rarity, price_bits, asset_id,
    compatible_rigs_json, catalog_version, active
FROM items;

DROP TABLE items;
ALTER TABLE items_reprice_rebuild RENAME TO items;
CREATE INDEX IF NOT EXISTS idx_items_slot_active ON items (slot, active);

PRAGMA foreign_keys = ON;

-- Epic band: 3,000-5,000 Bits. Common/uncommon/rare prices are unchanged.
UPDATE items SET price_bits = 3000 WHERE id = 'aura.spark_aura';
UPDATE items SET price_bits = 3200 WHERE id = 'aura.ember_halo';
UPDATE items SET price_bits = 3400 WHERE id = 'face.stack_trace';
UPDATE items SET price_bits = 3600 WHERE id = 'hat.bloom_filter';
UPDATE items SET price_bits = 3800 WHERE id = 'hat.lambda_tiara';
UPDATE items SET price_bits = 4000 WHERE id = 'front.usb_sword';
UPDATE items SET price_bits = 4200 WHERE id = 'aura.flame_wall';
UPDATE items SET price_bits = 4400 WHERE id = 'back.tiny_jetpack';
UPDATE items SET price_bits = 4600 WHERE id = 'back.webhook_wings';
UPDATE items SET price_bits = 4800 WHERE id = 'aura.starfield';
UPDATE items SET price_bits = 5000 WHERE id = 'title.pixel_pilot';

-- Legendary band: 12,000-25,000 Bits.
UPDATE items SET price_bits = 12000 WHERE id = 'face.laser_focus';
UPDATE items SET price_bits = 14000 WHERE id = 'back.glider_cloak';
UPDATE items SET price_bits = 16000 WHERE id = 'hat.cron_crown';
UPDATE items SET price_bits = 18000 WHERE id = 'front.pixel_blade';
UPDATE items SET price_bits = 22000 WHERE id = 'aura.rainbow_arc';
UPDATE items SET price_bits = 25000 WHERE id = 'hat.binary_crown';

-- Mythic prestige tier: 48,000-55,000 Bits. Each row reuses an existing launch-
-- 003 asset id, so no new art or manifest entry is needed.
INSERT OR IGNORE INTO items (
    id, name, slot, rarity, price_bits, asset_id,
    compatible_rigs_json, catalog_version, active
) VALUES
    ('aura.mythic_prism', 'Mythic Prism', 'aura', 'mythic', 50000,
     'aura.rainbow_arc', '["small_front_v1"]', 'launch-003', 1),
    ('hat.mythic_sovereign', 'Mythic Sovereign', 'head', 'mythic', 52000,
     'hat.binary_crown', '["small_front_v1"]', 'launch-003', 1),
    ('back.mythic_parallax', 'Mythic Parallax', 'back', 'mythic', 48000,
     'back.glider_cloak', '["small_front_v1"]', 'launch-003', 1),
    ('title.mythic_overclock', 'Mythic Overclock', 'title', 'mythic', 55000,
     'title.pixel_pilot', '["small_front_v1"]', 'launch-003', 1);
