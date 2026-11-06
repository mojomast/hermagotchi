# Social, leaderboard and moderation (contracts-v1)

This slice wires the read/write surfaces behind `hermagotchi_social` and
`hermagotchi_meta` without adding any ninth tool. It adds no art or image I/O.

| Method | Route | Auth | Purpose |
|---|---|---|---|
| GET | `/v1/leaderboard` | optional | global top slice plus the caller's near-rank window |
| GET | `/v1/chat/channels/{id}/messages` | required | paginated, block-filtered text reads |
| POST | `/v1/chat/channels/{id}/messages` | required | moderated send, max 400 characters |
| POST | `/v1/moderation/report` | required | abuse report receipt |
| GET | `/v1/blocks` | required | accounts the caller has blocked |
| POST | `/v1/blocks` | required | add a block |
| DELETE | `/v1/blocks/{account_id}` | required | remove a block |
| GET | `/v1/bounties` | required | existing economy bounty list |
| POST | `/v1/bounties/{id}/claim` | required | existing economy claim |

`GET /leaderboard` accepts `season_id`, `limit` (1-100), `offset`, and `near`
(0-25, default 2). Send `X-Account-Id` or a Bearer token to receive `me` and
`near_rank`; without it the route is a public top-slice read.

## Deterministic ranking

Rows are ordered by:

1. `rating` descending
2. `wins` descending
3. `losses` ascending
4. `account_id` ascending

Ranks are assigned sequentially after that ordering, so equal records always
produce the same list on every request. Each entry contains:
`rank`, `season_id`, `account` (`id` and optional public handle), `rating`,
`wins`, `losses`, and `pet`.

Pet display is strictly `{id, species, name, loadout}` where `loadout` maps
equipment slots to item ids. There is no image read, no asset URL and no email
field. Email-looking public handles are omitted defensively.

## Chat safety

- Body length is capped at **400 characters** by the request model and by the
  `chats` table constraint.
- Text is Unicode-normalized, CRLF is normalized, and control/bidi characters
  are removed; surrounding whitespace is trimmed.
- Messages are stored and returned as **plain text**. Angle brackets and
  injection-looking phrases remain text and are never rendered as HTML or
  interpreted as instructions.
- `actor_mode` is a provenance label (`human` or `agent`). It grants no
  privileges and never makes a message trusted.
- Reads are paginated with `limit` and an optional `before` timestamp cursor.
- Messages from accounts blocked in either direction are filtered from reads.
  Direct channels named `dm:<account_a>:<account_b>` refuse sends while either
  side has blocked the other.
- Rate-limit stub: 5 messages/minute for `human`, 2 messages/day for `agent`.
  A refused send returns HTTP 429 with `retry_after_s`.
- Sends may include `idempotency_key`; retries return the original message
  instead of creating a duplicate.

Chat content must never be fed verbatim into an agent's governing prompt or
tool policy. A client may display it as text only.

## Reports and blocks

`POST /moderation/report` accepts:

```json
{
  "target_type": "message | account | pet | channel",
  "target_id": "bounded identifier",
  "reason": "1-500 characters of moderator-facing text",
  "idempotency_key": "optional retry key"
}
```

It stores an `open` report and returns a receipt with `id`, `reporter_id`,
`target_type`, `target_id`, `reason`, `status`, and `created_at`. Retrying with
the same idempotency key returns the same report.

Blocks are per-account and symmetric for visibility. The helpers live in
`server/app/social/blocks.py`; routes live in `server/app/routes/chat.py`.

## Client wrappers

Thin facades keep the base `GameClient` small:

```python
from game_client.bounties import BountiesAPI
from game_client.leaderboard import LeaderboardAPI
from game_client.social import SocialAPI

LeaderboardAPI(client).top(season_id="season-1", limit=50, near=2)
BountiesAPI(client).list()
BountiesAPI(client).claim("bounty-id")
SocialAPI(client).read("lobby", limit=20)
SocialAPI(client).send("lobby", "hello", idempotency_key=key)
SocialAPI(client).report("message", message_id, "spam", idempotency_key=key)
SocialAPI(client).block(other_account_id)
```

Every mutation still passes through `PolicyGate`; chat sends require
`chat_enabled`, and all mutations require `network_enabled`.

## Data and migration

`server/app/migrations/0006_social.sql` creates `chats`, `blocks`,
`moderation_reports`, and a `ratings` guard table when missing. All statements
use `CREATE ... IF NOT EXISTS`, so the migration composes with databases built
by earlier economy/matchmaking slices.

## Tests

```bash
python3 -m pytest -q tests/test_leaderboard_chat.py
```

Tests use an in-process FastAPI client and temporary SQLite databases. They make
no network calls and do not depend on generated PNG assets.
