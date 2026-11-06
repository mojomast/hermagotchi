-- Friends, friend requests and last-seen presence (HGT-W14-A).
-- Forward-only. Accepted requests write friendships in both directions so a
-- lookup never has to scan a pair; only one pending request per ordered pair
-- is allowed by the partial unique index.

CREATE TABLE IF NOT EXISTS friend_requests (
    id TEXT PRIMARY KEY,
    from_account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    to_account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled')),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    CHECK (from_account_id <> to_account_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_friend_requests_pending_pair
    ON friend_requests (from_account_id, to_account_id)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_friend_requests_incoming
    ON friend_requests (to_account_id, status, created_at);

CREATE INDEX IF NOT EXISTS idx_friend_requests_outgoing
    ON friend_requests (from_account_id, status, created_at);

CREATE TABLE IF NOT EXISTS friendships (
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    friend_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (account_id, friend_id),
    CHECK (account_id <> friend_id)
);

CREATE INDEX IF NOT EXISTS idx_friendships_friend
    ON friendships (friend_id, account_id);

CREATE TABLE IF NOT EXISTS account_presence (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    last_seen_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_account_presence_last_seen
    ON account_presence (last_seen_at);
