# Hermagotchi Matchmaking — async challenges and matches

Status: wave-2 server slice. Implements the `contracts-v1` challenge/match flow
against the existing pure `battle-1` combat engine. No client may supply a
winner, damage value, replay hash, reward, or rating.

Routes are mounted under `/v1` by `server/app/main.py`:

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/challenges` | Invite an opponent, or start a practice bot challenge |
| `POST` | `/challenges/{id}/respond` | Accept or decline a pending challenge |
| `POST` | `/matches/{id}/tactics` | Lock one bounded tactic card for a participant |
| `GET` | `/matches/{id}` | Read the match header and resolved replay |

All routes require the injected account session (`X-Account-Id` in tests).
Only the two challenge participants may read a match or submit tactics.

## Modes

- `practice` — server bot match. The challenge is accepted immediately and a
  match is created; the challenger only submits their own card. The bot uses a
  fixed bounded card and `byteblob`. Practice never changes ratings.
- `casual` — two-account asynchronous match. Both participants must lock a
  tactic card.
- `ranked` — same flow as casual. Rating rows are updated only when a `ratings`
  table from another slice is present; practice and casual never touch it.

## Challenge creation

```http
POST /v1/challenges
{
  "defender_id": "<account-uuid>",
  "mode": "casual"
}
```

`opponent_id` is also accepted as an alias for `defender_id`. For `practice`
the defender may be omitted, or a bot-style string may be supplied; the server
normalizes it to the fixed practice bot identity. `expires_in_s` is optional
(default seven days, bounded 60 seconds to 30 days). An optional
`Idempotency-Key` header or `idempotency_key` body field returns the original
challenge for retries by the same challenger.

The response is a `Challenge` contract object with status `pending`, or
`accepted` for practice.

## Responding

```http
POST /v1/challenges/{id}/respond
{"action": "accept"}
```

`decision` and `response` are accepted as aliases for `action`. Only the
defender may respond for casual/ranked. Practice challenges are auto-accepted,
so responding is idempotent and returns the same match.

Response shape:

```json
{
  "challenge": {"contracts_version": "contracts-v1", "...": "..."},
  "match": {"contracts_version": "contracts-v1", "...": "..."}
}
```

`match` is `null` after a decline. Accepting after a decline is a conflict; a
declined challenge can be declined again idempotently. Expired invitations
cannot be accepted and are marked `expired`.

Match creation commits a server seed and `seed_commitment` (SHA-256 of the
seed). The seed and replay hash are hidden from the pending `Match` projection
and revealed only after resolution.

## Submitting tactics

```http
POST /v1/matches/{id}/tactics
{"card": {"ruleset_version": "battle-1", "stance": "aggressive", "actions": []}}
```

`tactics`, `tactic`, or a raw tactic card body are also accepted. Cards are
validated by `server.app.combat.validate_tactic_card`; unknown moves or
predicates are rejected with the engine's typed code (for example
`tactic_move_unknown`). Missing cards use the engine neutral default.

A participant's first accepted card is locked. Re-submitting the same card is
idempotent and returns the current match/replay. Re-submitting a different card
returns `409 tactics_locked`. Once both participant cards exist, or the practice
challenger locks against the bot card, the server resolves exactly once.

Response shape:

```json
{
  "match": {"contracts_version": "contracts-v1", "...": "..."},
  "replay": {"ruleset_version": "battle-1", "...": "..."}
}
```

`replay` is `null` until both cards are locked. `GET /v1/matches/{id}` returns
the same envelope, so both accounts see an identical replay event list and
`replay_hash`.

## Resolution and persistence

Resolution is centralized in
`server.app.matchmaking.resolve_pending_match`. It calls the pure engine:

```python
resolve_match("battle-1", pet_a, pet_b, card_a, card_b, committed_seed)
```

It then persists, in one transaction:

- `matches.status = 'resolved'`, `replay_hash`, winner, result, rounds and final HP;
- every replay event in `match_events` with a contiguous `seq` starting at 1;
- the challenge status `resolved`;
- optional ranked rating rows when a compatible `ratings` table exists;
- reward receipts.

The resolution update is guarded by `WHERE status = 'pending'`; a duplicate or
racing resolver reads the already-resolved row instead of persisting a second
result. Event inserts and entitlement inserts are also idempotent, so retries do
not create duplicate events or rewards.

## Rewards and economy bridge

Reward receipts are recorded in `reward_entitlements` with
`UNIQUE(match_id, account_id, kind)`. The slice records `bits` and `xp` kinds
for each eligible participant. Amounts follow `economy-1` hypotheses:

| Mode/result | Bits | XP |
|---|---:|---:|
| Practice bot (first 3 rewarded/day) | 10 | 15 |
| Casual win (first casual of UTC day adds 50/30) | 80 | 50 |
| Casual loss (first casual of UTC day adds 50/30) | 20 | 30 |
| Ranked win | 100 | 60 |
| Ranked loss | 25 | 35 |

`server/app/matchmaking/reward_bridge.py` records the receipt first, then tries
to apply it through `server.app.economy` if that package is importable. It
supports common `credit` / `award` / `grant` function shapes via signature
inspection. If the economy package is not present, credit is a no-op and the
entitlement row remains for later reconciliation. Integration with the economy
slice therefore keeps exactly-once awards: a duplicate resolution finds the
existing receipt and never calls the economy twice.

## Migration

`server/app/migrations/0003_matches.sql` adds:

- `challenges`
- `matches`
- `tactics`
- `match_events`
- `reward_entitlements` using `CREATE TABLE IF NOT EXISTS`, so an economy
  migration that already created the receipt table wins without an error.

The reward bridge inspects the live receipt table and writes the optional
`amount` column only when it exists; installations where another migrated table
owns the receipt schema still get idempotent rows.

## Practice and ratings

Practice resolves through the same engine and persistence path but never writes
ratings. It rewards only the human challenger and remains labeled
`mode = "practice"` on the challenge. Casual matches also leave ratings
untouched.

## Tests

```sh
python3 -m pytest -q server/tests/test_challenges_matches.py
```

The suite uses FastAPI `TestClient`, SQLite, and local fixtures only. It covers
two-account acceptance, tactic locking, one authoritative replay hash, practice
bot resolution, expired challenges, non-participant authorization, invalid
tactic codes, and duplicate submissions that must not double-award.
