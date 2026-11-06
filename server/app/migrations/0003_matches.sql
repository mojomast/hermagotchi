-- Async challenges, authoritative matches, locked tactics, replay events and
-- reward receipts. Every statement is safe to apply after a later economy
-- migration that may already create reward_entitlements.

CREATE TABLE IF NOT EXISTS challenges (
    id TEXT PRIMARY KEY,
    challenger_id TEXT NOT NULL REFERENCES accounts(id),
    defender_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('practice', 'casual', 'ranked')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'declined', 'expired', 'resolved')),
    idempotency_key TEXT,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_challenges_defender_status
    ON challenges (defender_id, status);
CREATE INDEX IF NOT EXISTS idx_challenges_challenger_status
    ON challenges (challenger_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_challenges_idempotency
    ON challenges (challenger_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    challenge_id TEXT NOT NULL UNIQUE REFERENCES challenges(id),
    ruleset_version TEXT NOT NULL,
    economy_version TEXT NOT NULL,
    seed_commitment TEXT NOT NULL,
    seed TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'resolved', 'expired')),
    replay_hash TEXT,
    winner TEXT,
    result TEXT,
    rounds INTEGER,
    final_hp_json TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_matches_status ON matches (status);

CREATE TABLE IF NOT EXISTS tactics (
    match_id TEXT NOT NULL REFERENCES matches(id),
    account_id TEXT NOT NULL,
    card_json TEXT NOT NULL,
    locked_at TEXT NOT NULL,
    UNIQUE (match_id, account_id)
);

CREATE TABLE IF NOT EXISTS match_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL REFERENCES matches(id),
    seq INTEGER NOT NULL CHECK (seq >= 1),
    event_json TEXT NOT NULL,
    UNIQUE (match_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_match_events_match_seq
    ON match_events (match_id, seq);

CREATE TABLE IF NOT EXISTS reward_entitlements (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    amount INTEGER NOT NULL DEFAULT 0,
    awarded_at TEXT NOT NULL,
    UNIQUE (match_id, account_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_reward_entitlements_match
    ON reward_entitlements (match_id);
