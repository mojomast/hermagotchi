-- Agent chat, DM inbox cursors and post-match taunts (HGT-W13-A).
-- Forward-only. SQLite cannot add a CHECK constraint to an existing column,
-- and the original chats.channel_id cap (64) is too short for a canonical
-- dm:<account_a>:<account_b> channel, so chats is rebuilt in place. Rows,
-- indexes and the body/idempotency guards are preserved exactly.

PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS chats_w13_rebuild;
CREATE TABLE chats_w13_rebuild (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL CHECK (length(channel_id) BETWEEN 1 AND 128),
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    actor_mode TEXT NOT NULL DEFAULT 'human'
        CHECK (actor_mode IN ('human', 'agent')),
    body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 400),
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    deleted_at TEXT,
    kind TEXT DEFAULT 'chat'
        CHECK (kind IS NULL OR kind IN ('chat', 'taunt')),
    match_id TEXT,
    match_context_json TEXT
);

INSERT INTO chats_w13_rebuild (
    id, channel_id, account_id, actor_mode, body,
    idempotency_key, created_at, deleted_at, kind, match_id,
    match_context_json
)
SELECT
    id, channel_id, account_id, actor_mode, body,
    idempotency_key, created_at, deleted_at, 'chat', NULL, NULL
FROM chats;

DROP TABLE chats;
ALTER TABLE chats_w13_rebuild RENAME TO chats;

CREATE INDEX IF NOT EXISTS idx_chats_channel_created
    ON chats (channel_id, created_at, id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_chats_idempotency
    ON chats (account_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chats_kind_match
    ON chats (kind, match_id);

CREATE INDEX IF NOT EXISTS idx_chats_account_created
    ON chats (account_id, created_at);

PRAGMA foreign_keys = ON;

-- Per-account read marker for the combined DM/@mention inbox. A row with
-- channel_id = 'inbox' tracks the global cursor; channel rows are also
-- supported for per-conversation markers.
CREATE TABLE IF NOT EXISTS chat_read_cursors (
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    channel_id TEXT NOT NULL CHECK (length(channel_id) BETWEEN 1 AND 128),
    last_read_at TEXT NOT NULL,
    PRIMARY KEY (account_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_read_cursors_account
    ON chat_read_cursors (account_id, last_read_at);

-- Desktop/owner toggle for agent-authored chat. Humans are never gated by it.
CREATE TABLE IF NOT EXISTS account_chat_settings (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    agent_chat_enabled INTEGER NOT NULL DEFAULT 0
        CHECK (agent_chat_enabled IN (0, 1)),
    updated_at TEXT NOT NULL
);
