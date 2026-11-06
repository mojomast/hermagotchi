-- signup caps (HGT-W10-Z). Forward-only.
--
-- accounts.created_ip is nullable so rows created before this migration keep
-- working. signup_ip_stats holds lifetime per-IP registration counts that are
-- incremented in the same transaction as each new-account insert.

ALTER TABLE accounts ADD COLUMN created_ip TEXT;

CREATE TABLE IF NOT EXISTS signup_ip_stats (
    ip TEXT PRIMARY KEY,
    signup_count INTEGER NOT NULL DEFAULT 0,
    first_signup_at TEXT,
    last_signup_at TEXT
);
