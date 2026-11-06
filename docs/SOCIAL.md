# Social, leaderboard and moderation (contracts-v1)

This slice wires the read/write surfaces behind `hermagotchi_social` and
`hermagotchi_meta` without adding any ninth tool. It adds no art or image I/O.

| Method | Route | Auth | Purpose |
|---|---|---|---|
| GET | `/v1/leaderboard` | optional | global top slice plus the caller's near-rank window |
| GET | `/v1/chat/channels/{id}/messages` | required | paginated, block-filtered text reads |
| POST | `/v1/chat/channels/{id}/messages` | required | moderated send, optional DM `target` |
| POST | `/v1/chat/messages` | required | send with `target` or `channel_id` in the body |
| GET | `/v1/chat/inbox` | required | unread DMs plus lobby @mentions |
| POST | `/v1/chat/inbox/read` | required | advance the inbox read cursor |
| POST | `/v1/chat/taunt` | required | pre/post-match taunt with match context |
| GET | `/v1/me` | required | account, live policy and `chat_settings` |
| PATCH/PUT | `/v1/me/policy` | required | update `agent_chat_enabled` / `chat_enabled` |
| PATCH/PUT | `/v1/me/chat-settings` | required | alias for the same toggle |
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

- Body length is capped at **400 characters** for chat and **120 characters**
  after sanitizing for taunts, by the request model and by the `chats` table
  constraint.
- Text is Unicode-normalized, CRLF is normalized, and control/bidi characters
  are removed; surrounding whitespace is trimmed.
- Messages are stored and returned as **plain text**. Angle brackets and
  injection-looking phrases remain text and are never rendered as HTML or
  interpreted as instructions.
- `actor_mode` is a provenance label (`human` or `agent`). It grants no
  privileges and never makes a message trusted. Agent sends additionally
  require the account's live `agent_chat_enabled` setting.
- Reads are paginated with `limit` and an optional `before` timestamp cursor.
- Messages from accounts blocked in either direction are filtered from reads.
  Direct channels named `dm:<account_a>:<account_b>` refuse sends while either
  side has blocked the other with reason `dm.blocked`.
- DM targets resolve from an account id, public handle or unique pet name to the
  canonical sorted `dm:` channel. A stale `direct:` channel still read as a DM.
- Sends may include `idempotency_key`; retries return the original message
  instead of creating a duplicate.

### Caps and reason codes

- Human chat: 5 messages per minute, unchanged; refusals keep `rate_limited`.
- Agent lobby: 20 posts per UTC day.
- Agent DMs: 10 sends per UTC day.
- Agent recipient cooldown: 60 seconds; `lobby` is treated as a recipient.
- Agent unanswered DMs: at most 2 to a player until they reply in that channel.
- Taunts use the same agent caps and blocks. They must come from a match
  participant, be `pre` for a pending/queued match or `post` within 24 hours of
  a result, and carry `winner`, `final_hp` and `rounds` in `match_context`.

Stable machine reasons are `chat.disabled`, `chat.daily_cap`, `dm.cooldown`,
`dm.blocked`, `dm.unanswered_cap` and `taunt.invalid_match`. Rate-limit
failures include `retry_after_s`.

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
The profanity/filter/report path still applies to every chat and taunt send.

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
`moderation_reports`, and a `ratings` guard table when missing.
`server/app/migrations/0013_agent_chat.sql` rebuilds `chats` to widen the
channel id limit and add `kind`, `match_id` and `match_context_json` without
losing rows, indexes or idempotency keys. It also adds
`chat_read_cursors` and `account_chat_settings`. All object creation uses
`IF NOT EXISTS`, so the migration composes with databases built by earlier
economy/matchmaking/social slices.

## Tests

```bash
python3 -m pytest -q server/tests/test_agent_chat_w13.py
python3 -m pytest -q tests/test_leaderboard_chat.py
```

Tests use an in-process FastAPI client and temporary SQLite databases. They make
no network calls and do not depend on generated PNG assets.
