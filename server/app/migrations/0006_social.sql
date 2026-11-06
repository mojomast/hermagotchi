-- contracts-v1 social slice (HGT-W5-M): chat, blocks, moderation reports and
-- an idempotent ratings guard. Every table is created only when missing so a
-- later merge that already added one of these objects stays safe.
--
-- chats.body is plain text (never markup) constrained to 400 characters.
-- Idempotency keys are optional but make client retries exact.

CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL CHECK (length(channel_id) BETWEEN 1 AND 64),
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    actor_mode TEXT NOT NULL DEFAULT 'human'
        CHECK (actor_mode IN ('human', 'agent')),
    body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 400),
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_chats_channel_created
    ON chats (channel_id, created_at, id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_chats_idempotency
    ON chats (account_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS blocks (
    blocker_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    blocked_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (blocker_id, blocked_id)
);

CREATE INDEX IF NOT EXISTS idx_blocks_blocked
    ON blocks (blocked_id, blocker_id);

CREATE TABLE IF NOT EXISTS moderation_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL
        CHECK (target_type IN ('message', 'account', 'pet', 'channel')),
    target_id TEXT NOT NULL CHECK (length(target_id) BETWEEN 1 AND 128),
    reason TEXT NOT NULL CHECK (length(reason) BETWEEN 1 AND 500),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'reviewed', 'closed')),
    idempotency_key TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_moderation_reports_status
    ON moderation_reports (status, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_moderation_reports_idempotency
    ON moderation_reports (reporter_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- Ratings normally arrive with 0002_economy.sql; this guard covers databases
-- that predate that migration or were built from a partial schema.
CREATE TABLE IF NOT EXISTS ratings (
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    season_id TEXT NOT NULL,
    rating INTEGER NOT NULL DEFAULT 1000 CHECK (rating >= 0),
    wins INTEGER NOT NULL DEFAULT 0 CHECK (wins >= 0),
    losses INTEGER NOT NULL DEFAULT 0 CHECK (losses >= 0),
    UNIQUE (account_id, season_id)
);

CREATE INDEX IF NOT EXISTS idx_ratings_season_order
    ON ratings (season_id, rating DESC, wins DESC, account_id);
