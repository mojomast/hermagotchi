-- contracts-v1 auth addendum (HGT-W7): device pairing, device records and
-- hashed auth sessions. Forward-only.
--
-- Raw access tokens (hga_), refresh tokens (hgr_) and device codes (hgd_) are
-- never stored. Each hash column contains the lowercase SHA-256 hex digest of
-- the raw value. user_code is a short human-visible approval code, not a
-- bearer credential, and is stored normalized (uppercase, no separators).

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    device_name TEXT NOT NULL CHECK (length(device_name) BETWEEN 1 AND 64),
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_devices_account
    ON devices (account_id, created_at);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    access_token_hash TEXT NOT NULL UNIQUE,
    refresh_token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    access_expires_at TEXT NOT NULL,
    refresh_expires_at TEXT NOT NULL,
    last_used_at TEXT,
    rotated_at TEXT,
    revoked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_device
    ON auth_sessions (device_id);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_account
    ON auth_sessions (account_id, created_at);

CREATE TABLE IF NOT EXISTS pairings (
    id TEXT PRIMARY KEY,
    device_code_hash TEXT NOT NULL UNIQUE,
    user_code TEXT NOT NULL,
    device_name TEXT NOT NULL CHECK (length(device_name) BETWEEN 1 AND 64),
    new_account INTEGER NOT NULL DEFAULT 0 CHECK (new_account IN (0, 1)),
    public_handle TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    approved_at TEXT,
    approved_account_id TEXT REFERENCES accounts(id) ON DELETE SET NULL,
    used_at TEXT,
    last_poll_at TEXT,
    interval_s INTEGER NOT NULL DEFAULT 5 CHECK (interval_s > 0)
);

CREATE INDEX IF NOT EXISTS idx_pairings_user_code
    ON pairings (user_code, created_at);

CREATE INDEX IF NOT EXISTS idx_pairings_device_code
    ON pairings (device_code_hash);
