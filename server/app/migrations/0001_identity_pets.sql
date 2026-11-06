-- contracts-v1 baseline: identity and one pet per account.
-- Wallet, ledger, combat, shop and chat tables land in later slices.

CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    public_handle TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    privacy_flags TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE pets (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL UNIQUE REFERENCES accounts(id),
    species TEXT NOT NULL CHECK (species IN ('byteblob', 'patchfox', 'nullgeist')),
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

CREATE INDEX idx_pets_account_id ON pets (account_id);
