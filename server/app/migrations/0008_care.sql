-- contracts-v1 care addendum (HGT-W8-S): idempotent feed/play/rest receipts.
-- Forward-only. Care itself keeps using pets.care_json / care_updated_at; this
-- table only records the once-per-idempotency-key receipt and cooldown anchor.
-- Raw client idempotency keys are short-lived request identifiers, never auth
-- material.

CREATE TABLE IF NOT EXISTS care_events (
    id TEXT PRIMARY KEY,
    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('feed', 'play', 'rest')),
    idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 128),
    care_json TEXT NOT NULL,
    care_updated_at TEXT NOT NULL,
    cooldown_until TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (account_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_care_events_pet_action
    ON care_events (pet_id, action, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_care_events_account
    ON care_events (account_id, created_at DESC);
