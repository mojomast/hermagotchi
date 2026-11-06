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

## Starter Bits

Every account receives a one-time **300 Bit** starter grant when it first
adopts a pet (`POST /v1/pets`). The credit uses ledger reason
`economy.starter_grant` with source event `economy.starter_grant:<account_id>`,
so it is idempotent: retries and the once-per-account adopt rule can never
grant it twice.

Migration `0011_starter_and_rate_limits.sql` backfills the same grant for
accounts that predate the adopt-time credit. An account is eligible only when
it has no inventory purchase rows, no existing starter grant, and its wallet
balance is below 300 Bits. Accounts that already purchased something, or that
already hold at least 300 Bits, are left untouched.

## Income sources and caps

Bits enter the economy only through server-owned rewards. The complete regular
income picture is:

| Source | Reward | Cap |
|---|---|---|
| Starter grant | 300 Bits once | Once per account |
| Practice (Teknium) | 50 Bits per rewarded practice | First **3** rewarded practices per UTC day; **750 Bits per ISO week (UTC)** |
| PvP matches | Match reward | Bits for at most **10** matches per UTC day, and at most **2** matches against the same opponent per UTC day |
| Bounties | Bounty-defined Bits (`{"bits": 100, "xp": 20}` for the seeded dailies) | Unchanged: one claim per `(account_id, bounty_id)` |

The practice daily cap and the starter grant are part of the current server
slice. The 750-Bits-per-ISO-week practice cap and the PvP daily/opponent caps
are the income-cap work owned by the HGT-W12-B slice; this document is the
single authoritative description of the intended economy while that slice
lands. No client may mint Bits by submitting a reward, price, or balance.

A regular player who claims practice plus a normal share of PvP and bounties
earns roughly **300-500 Bits/day**, with active PvP players reaching the upper
end of that band.

## Practice rewards

The Teknium practice opponent (battle-2, ratings never change) pays **50 Bits**
and 15 XP for each of the first **3 rewarded practices per UTC day**. A full
day of rewarded practice therefore funds the cheapest 150-Bit catalog item on
its own. The fourth and later practices on the same day still resolve and
return a replay, but produce no Bits or XP.

The HGT-W12-B practice cap additionally limits practice Bits to **750 Bits per
ISO week (UTC)**, so a seven-day practice-only streak cannot exceed that weekly
total even when the UTC day rolls over.

## Cosmetic price bands

Catalog prices are frozen server data. Common, uncommon and rare items stay at
their flat launch prices; epic and legendary items were repriced upward in
migration `0012_economy_reprice_mythic.sql`, and the mythic prestige tier was
added at the same time.

| Rarity | Price band | Intent |
|---|---:|---|
| common | 150 Bits | First-session purchase |
| uncommon | 350 Bits | A day or two of regular play |
| rare | 700 Bits | About a week of regular play |
| epic | 3,000-5,000 Bits | Multi-week goal |
| legendary | 12,000-25,000 Bits | Long-term flex |
| mythic | 48,000-55,000 Bits | Prestige sink for veterans |

### Epic (exact prices)

| Item | Bits |
|---|---:|
| `aura.spark_aura` | 3,000 |
| `aura.ember_halo` | 3,200 |
| `face.stack_trace` | 3,400 |
| `hat.bloom_filter` | 3,600 |
| `hat.lambda_tiara` | 3,800 |
| `front.usb_sword` | 4,000 |
| `aura.flame_wall` | 4,200 |
| `back.tiny_jetpack` | 4,400 |
| `back.webhook_wings` | 4,600 |
| `aura.starfield` | 4,800 |
| `title.pixel_pilot` | 5,000 |

### Legendary (exact prices)

| Item | Bits |
|---|---:|
| `face.laser_focus` | 12,000 |
| `back.glider_cloak` | 14,000 |
| `hat.cron_crown` | 16,000 |
| `front.pixel_blade` | 18,000 |
| `aura.rainbow_arc` | 22,000 |
| `hat.binary_crown` | 25,000 |

### Mythic prestige tier (exact prices)

Mythic items are cosmetic-only prestige variants. Each one reuses an existing
launch-003 `asset_id`, so there is no new art and no new manifest entry.

| Item | Slot | Reused asset | Bits |
|---|---|---|---:|
| `back.mythic_parallax` | back | `back.glider_cloak` | 48,000 |
| `aura.mythic_prism` | aura | `aura.rainbow_arc` | 50,000 |
| `hat.mythic_sovereign` | head | `hat.binary_crown` | 52,000 |
| `title.mythic_overclock` | title | `title.pixel_pilot` | 55,000 |

### Expected time to a prestige item

At roughly **300-500 Bits/day**:

- **Legendary: ~2-4 weeks.** The entry legendary is 12,000 Bits, about 24 days
  at 500 Bits/day; bounties and a strong PvP week put the whole range inside
  that window. At a strict 300 Bits/day the cheapest legendary takes about six
  weeks, and the 25,000-Bit crown is a longer goal.
- **Mythic: ~2-3 months.** The cheapest mythic is 48,000 Bits, about 96 days at
  500 Bits/day and close to three months once bounty income is included. At a
  strict 300 Bits/day it stretches toward five months; the 55,000-Bit title is
  the longest prestige goal.

The intent is replay value, not a wall: each band should feel reachable with
consistent play while keeping the top tier visibly rare.

## Durable auth rate limits

Migration `0011_starter_and_rate_limits.sql` also adds `auth_rate_hits` and
`auth_rate_locks`. The auth routes pass their SQLite connection to
`AuthRateLimiter`, so the pair/start IP window and the 5-failure approve
lockout survive a new limiter instance and are shared across uvicorn workers.

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
bounty rows themselves are trusted server data. Bounty income and claim limits
are unchanged by the repricing migration.

## Scope

This document covers the Bits ledger, starter grant, practice income, bounty
income, and the cosmetic price bands consumed by the shop. Shop purchases,
inventory and equipment use these ledger primitives; matchmaking and combat
ratings remain separate slices. The income caps described above are enforced by
the HGT-W12-B slice, not by the repricing migration.

## Tests

```bash
python3 -m pytest -q server/tests/test_economy_ledger.py
python3 -m pytest -q server/tests/test_economy_reprice.py server/tests/test_shop.py
```

The suites cover the wallet/ledger invariant, 100 identical concurrent retries
producing one ledger row, overdraft refusal, entitlement replay, bounty
one-time claims, pagination, account isolation, the repriced epic/legendary
bands, the mythic tier, and mythic purchases. No network is used.
