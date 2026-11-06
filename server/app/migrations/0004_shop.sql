-- contracts-v1 shop slice (HGT-W2-G): catalog, ownership and equipped loadout.
-- Purchases debit the economy ledger and grant inventory in one write
-- transaction. inventory.source_event_id is unique, so an idempotency key can
-- never create a second debit or a second ownership row.

CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY
        CHECK (id GLOB '[a-z]*.[a-z0-9_]*' AND length(id) BETWEEN 3 AND 64),
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 48),
    slot TEXT NOT NULL
        CHECK (slot IN ('head', 'face', 'back', 'front', 'aura', 'emote', 'habitat', 'title')),
    rarity TEXT NOT NULL
        CHECK (rarity IN ('common', 'uncommon', 'rare', 'epic', 'legendary')),
    price_bits INTEGER NOT NULL CHECK (price_bits >= 0),
    asset_id TEXT NOT NULL CHECK (length(asset_id) BETWEEN 1 AND 64),
    compatible_rigs_json TEXT NOT NULL,
    catalog_version TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_items_slot_active ON items (slot, active);

CREATE TABLE IF NOT EXISTS inventory (
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES items(id),
    acquired_at TEXT NOT NULL,
    source_event_id TEXT NOT NULL UNIQUE
        CHECK (length(source_event_id) BETWEEN 1 AND 128),
    PRIMARY KEY (account_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_inventory_account
    ON inventory (account_id, acquired_at);

CREATE TABLE IF NOT EXISTS equipment (
    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    slot TEXT NOT NULL
        CHECK (slot IN ('head', 'face', 'back', 'front', 'aura', 'emote', 'habitat', 'title')),
    item_id TEXT NOT NULL REFERENCES items(id),
    equipped_at TEXT NOT NULL,
    PRIMARY KEY (pet_id, slot)
);

CREATE INDEX IF NOT EXISTS idx_equipment_item ON equipment (item_id);

INSERT OR IGNORE INTO items (
    id, name, slot, rarity, price_bits, asset_id,
    compatible_rigs_json, catalog_version, active
) VALUES
    ('hat.binary_crown', 'Binary Crown', 'head', 'legendary', 2000,
     'hat.binary_crown', '["small_front_v1"]', 'launch-001', 1),
    ('hat.wizard_hat', 'Packet Wizard Hat', 'head', 'rare', 700,
     'hat.wizard_hat', '["small_front_v1"]', 'launch-001', 1),
    ('face.scan_visor', 'Scan Visor', 'face', 'uncommon', 350,
     'face.scan_visor', '["small_front_v1"]', 'launch-001', 1),
    ('back.circuit_cape', 'Circuit Cape', 'back', 'rare', 700,
     'back.circuit_cape', '["small_front_v1"]', 'launch-001', 1),
    ('front.pixel_badge', 'Pixel Badge', 'front', 'common', 150,
     'front.pixel_badge', '["small_front_v1"]', 'launch-001', 1),
    ('aura.spark_aura', 'Spark Aura', 'aura', 'epic', 1200,
     'aura.spark_aura', '["small_front_v1"]', 'launch-001', 1),
    ('emote.sparkle', 'Sparkle Emote', 'emote', 'common', 150,
     'emote.sparkle', '["small_front_v1"]', 'launch-001', 1),
    ('habitat.glow_moss', 'Glow Moss Shelf', 'habitat', 'uncommon', 350,
     'habitat.glow_moss', '["small_front_v1"]', 'launch-001', 1),
    ('title.pixel_pilot', 'Pixel Pilot Title', 'title', 'epic', 1200,
     'title.pixel_pilot', '["small_front_v1"]', 'launch-001', 1);
