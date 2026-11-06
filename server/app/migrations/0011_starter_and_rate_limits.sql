-- Starter economy and durable auth rate limits (HGT-W11-A). Forward-only.
--
-- 1) Durable rate-limit tables shared by every uvicorn worker. Times are unix
--    seconds as REAL so they line up with server.app.auth.now_ts().
-- 2) One-time 300 Bit starter grant for accounts that predate the adopt-time
--    grant: no purchase rows, balance below 300, and no starter grant yet.

CREATE TABLE IF NOT EXISTS auth_rate_hits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    stamped_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_rate_hits_key
    ON auth_rate_hits (key, stamped_at);

CREATE TABLE IF NOT EXISTS auth_rate_locks (
    key TEXT PRIMARY KEY,
    until_at REAL NOT NULL,
    failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_auth_rate_locks_until
    ON auth_rate_locks (until_at);

DROP TABLE IF EXISTS temp._starter_grant_accounts;

CREATE TEMP TABLE _starter_grant_accounts AS
SELECT a.id AS account_id
FROM accounts AS a
LEFT JOIN wallets AS w ON w.account_id = a.id
WHERE COALESCE(w.balance, 0) < 300
  AND NOT EXISTS (
      SELECT 1 FROM inventory AS i WHERE i.account_id = a.id
  )
  AND NOT EXISTS (
      SELECT 1 FROM ledger AS l
      WHERE l.account_id = a.id AND l.reason LIKE 'shop.%'
  )
  AND NOT EXISTS (
      SELECT 1 FROM ledger AS l
      WHERE l.account_id = a.id AND l.reason = 'economy.starter_grant'
  );

INSERT OR IGNORE INTO wallets (account_id, balance, revision)
SELECT account_id, 0, 0 FROM _starter_grant_accounts;

INSERT INTO ledger (
    id, account_id, delta, reason, source_event_id, balance_after, created_at
)
SELECT
    lower(hex(randomblob(16))),
    s.account_id,
    300,
    'economy.starter_grant',
    'economy.starter_grant:' || s.account_id,
    w.balance + 300,
    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
FROM _starter_grant_accounts AS s
JOIN wallets AS w ON w.account_id = s.account_id;

UPDATE wallets
SET balance = balance + 300,
    revision = revision + 1
WHERE account_id IN (SELECT account_id FROM _starter_grant_accounts);

DROP TABLE _starter_grant_accounts;
