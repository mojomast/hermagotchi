-- contracts-v1 economy slice (HGT-W2-E): wallets, append-only ledger,
-- once-only reward entitlements, daily bounties and an Elo ratings stub.
-- The invariant enforced by the application layer is:
--   wallets.balance == SUM(ledger.delta) for the same account_id.

CREATE TABLE wallets (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0)
);

CREATE TABLE ledger (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    delta INTEGER NOT NULL,
    reason TEXT NOT NULL CHECK (length(reason) BETWEEN 1 AND 64),
    source_event_id TEXT NOT NULL UNIQUE
        CHECK (length(source_event_id) BETWEEN 1 AND 128),
    balance_after INTEGER NOT NULL DEFAULT 0 CHECK (balance_after >= 0),
    created_at TEXT NOT NULL
);

CREATE INDEX idx_ledger_account_created
    ON ledger (account_id, created_at DESC);

CREATE TABLE reward_entitlements (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    bits INTEGER NOT NULL DEFAULT 0 CHECK (bits >= 0),
    xp INTEGER NOT NULL DEFAULT 0 CHECK (xp >= 0),
    ledger_id TEXT REFERENCES ledger(id),
    awarded_at TEXT NOT NULL,
    UNIQUE (match_id, account_id, kind)
);

CREATE INDEX idx_reward_entitlements_account
    ON reward_entitlements (account_id, awarded_at);

CREATE TABLE bounties (
    id TEXT PRIMARY KEY,
    starts_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    rule_json TEXT NOT NULL,
    reward_json TEXT NOT NULL,
    title TEXT,
    description TEXT,
    max_claims INTEGER NOT NULL DEFAULT 1 CHECK (max_claims >= 1),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT
);

CREATE INDEX idx_bounties_window ON bounties (active, starts_at, expires_at);

CREATE TABLE bounty_claims (
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    bounty_id TEXT NOT NULL REFERENCES bounties(id) ON DELETE CASCADE,
    claimed_at TEXT NOT NULL,
    ledger_id TEXT REFERENCES ledger(id),
    reward_bits INTEGER NOT NULL DEFAULT 0 CHECK (reward_bits >= 0),
    reward_xp INTEGER NOT NULL DEFAULT 0 CHECK (reward_xp >= 0),
    UNIQUE (account_id, bounty_id)
);

CREATE INDEX idx_bounty_claims_account ON bounty_claims (account_id, claimed_at);

-- Rating stub: populated by the later matches/leaderboard slice.
CREATE TABLE ratings (
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    season_id TEXT NOT NULL,
    rating INTEGER NOT NULL DEFAULT 1000 CHECK (rating >= 0),
    wins INTEGER NOT NULL DEFAULT 0 CHECK (wins >= 0),
    losses INTEGER NOT NULL DEFAULT 0 CHECK (losses >= 0),
    UNIQUE (account_id, season_id)
);
