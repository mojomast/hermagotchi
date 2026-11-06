-- contracts-v1 owner goal persistence (HGT-W5-L).
-- One active goal per account; clearing keeps an audit row. CREATE IF NOT EXISTS
-- keeps replaying this migration safe in local SQLite databases.

CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('cosmetic', 'rank', 'achievement')),
    target_id TEXT NOT NULL CHECK (length(target_id) BETWEEN 1 AND 64),
    chosen_by TEXT NOT NULL
        CHECK (chosen_by IN ('human', 'agent', 'co-op', 'coop')),
    chosen_at TEXT NOT NULL,
    spending_limit_bits INTEGER NOT NULL DEFAULT 0
        CHECK (spending_limit_bits >= 0),
    max_battles INTEGER NOT NULL DEFAULT 0 CHECK (max_battles >= 0),
    expires_at TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'cleared', 'expired')),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    idempotency_key TEXT
);

CREATE INDEX IF NOT EXISTS idx_goals_account_status
    ON goals (account_id, status, chosen_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_goals_one_active
    ON goals (account_id) WHERE status = 'active';

CREATE UNIQUE INDEX IF NOT EXISTS idx_goals_idempotency
    ON goals (account_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
