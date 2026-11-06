-- launch-003 catalog + species expansion (HGT-W10-Y).
-- Forward-only migration. Existing pets, inventory, equipment and care_events
-- rows are preserved.

-- 1) The launch-003 roster replaces the launch-001 three-species CHECK. SQLite
-- cannot alter a CHECK in place, so rebuild pets with the same columns plus the
-- ten-species allowlist while foreign keys are disabled (children keep pointing
-- at "pets" and no ON DELETE CASCADE fires).
PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS pets_launch003_rebuild;
CREATE TABLE pets_launch003_rebuild (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL UNIQUE REFERENCES accounts(id),
    species TEXT NOT NULL CHECK (species IN (
        'byteblob', 'patchfox', 'nullgeist', 'kernelcrab', 'cachebat',
        'stacktoise', 'daemowl', 'shellsnail', 'regexopus', 'firewyrm'
    )),
    name TEXT NOT NULL,
    appearance_seed TEXT NOT NULL,
    traits_json TEXT NOT NULL,
    stats_json TEXT NOT NULL,
    care_json TEXT NOT NULL,
    care_updated_at TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1 CHECK (level >= 1),
    xp INTEGER NOT NULL DEFAULT 0 CHECK (xp >= 0),
    created_at TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1)
);

INSERT INTO pets_launch003_rebuild (
    id, account_id, species, name, appearance_seed, traits_json, stats_json,
    care_json, care_updated_at, level, xp, created_at, revision
)
SELECT
    id, account_id, species, name, appearance_seed, traits_json, stats_json,
    care_json, care_updated_at, level, xp, created_at, revision
FROM pets;

DROP TABLE pets;
ALTER TABLE pets_launch003_rebuild RENAME TO pets;
CREATE INDEX IF NOT EXISTS idx_pets_account_id ON pets (account_id);

PRAGMA foreign_keys = ON;

-- 2) 0004_shop.sql and 0008_cosmetics_pack.sql already seed every one of the 81
-- launch-003 manifest asset ids that are shop items, so no INSERT is required.
-- Advance the catalog version without touching inventory or equipment rows.
UPDATE items SET catalog_version = 'launch-003' WHERE active = 1;
