# Economy (economy-1)

Authoritative Bits economy for the hosted service. The server owns every
balance change; clients never submit a price, reward, or balance.

## Invariants

- `wallets.balance == SUM(ledger.delta)` for each account.
- Wallets never go below zero.
- `ledger.source_event_id` is globally unique. Retrying the same source event
  returns the original ledger receipt and never credits twice.
- `reward_entitlements` is unique on `(match_id, account_id, kind)`, so replaying
  a completed match cannot duplicate Bits or XP.
- `bounty_claims` is unique on `(account_id, bounty_id)`, so a daily bounty pays
  at most once per account.
- Each wallet change, ledger row, entitlement/claim row, and pet XP update is
  committed in one write transaction. SQLite uses `BEGIN IMMEDIATE` to serialize
  writers; production multi-worker deployments should use PostgreSQL row locks.

## Service API (`server/app/economy/`)

| Helper | Purpose |
|---|---|
| `ensure_wallet(conn, account_id)` | Create/read the zero-balance wallet projection. |
| `credit(conn, account_id, amount, reason, source_event_id)` | Add Bits once per source event. |
| `debit(conn, account_id, amount, reason, source_event_id)` | Remove Bits once per source event; raises `InsufficientFunds` rather than going negative. |
| `grant_entitlement(conn, match_id, account_id, kind, bits, xp)` | Award a match reward and pet XP exactly once. |
| `claim_bounty(conn, bounty_id, account_id)` | Validate an active bounty, credit its reward, and record the one-time claim. |

All receipt payloads match the frozen `LedgerEntry` contract.

## HTTP routes

| Method | Route | Notes |
|---|---|---|
| GET | `/v1/wallet` | Wallet projection; creates a zero wallet on first read. |
| GET | `/v1/ledger?limit=&offset=` | Newest-first, account-scoped history. `limit` is 1-100; response includes `entries`, `total`, and `next_offset`. |
| GET | `/v1/bounties` | Active bounties for the authenticated account with `claimed`/`claimable`. |
| POST | `/v1/bounties/{id}/claim` | One-time reward; retries return the same receipt and wallet. |

Every route derives the account from the authenticated session and never
accepts `account_id` from the request body.

## Bounties

Migration `0002_economy.sql` adds `wallets`, `ledger`,
`reward_entitlements`, `bounties`, `bounty_claims`, and a `ratings` stub.
Bounties are server-seeded with `starts_at`, `expires_at`, `rule_json`, and
`reward_json` (`{"bits": 100, "xp": 20}`). Supported automated predicates are
`always`/`daily`, `ledger_reason_count`, `ledger_reason_sum`, and `min_balance`;
predicates owned by the later matchmaking slice remain claimable because the
bounty rows themselves are trusted server data.

## Scope

This slice does not implement shop purchases, inventory, matchmaking, ratings
updates, or transfers. Those build on the same ledger primitives.

## Tests

```bash
python3 -m pytest -q server/tests/test_economy_ledger.py
```

The suite covers the wallet/ledger invariant, 100 identical concurrent retries
producing one ledger row, overdraft refusal, entitlement replay, bounty
one-time claims, pagination, and account isolation. No network is used.
