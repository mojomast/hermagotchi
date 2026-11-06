# HERMAGOTCHI — Frozen Contracts (contracts-v1)

**Prepared:** 2026-11-05 (America/Toronto)  
**Source:** `/workspace/newplugin/hermagotchi/{SPEC.md,DEVPLAN.md}`  
**Deadline:** 2026-11-11 5:00 PM ET  
**Status:** PREPARE ONLY — not yet tagged in a git repo (repo `mojomast/hermagotchi` does not exist yet).

This document is the integrator-owned contract freeze for Orbit bees. All wave-1+ slices implement against these names. Changing a contract requires an orchestrator note in `ORCH.md` and fixture updates before dependent bees dispatch.

---

## 1. Repository layout

Target unified Hermes package + separable hosted service (mirrors `mojomast/hermes-godseye` / `mojomast/hermes-shortrizz` packaging):

```
hermagotchi/
  README.md LICENSE SPEC.md DEVPLAN.md
  plugin.yaml                      # agent plugin manifest
  __init__.py                      # register(ctx) only
  schemas.py                       # LLM tool JSON schemas (compact)
  tools.py                         # tool handlers → game_client
  skills/hermagotchi/SKILL.md
  game_client/                     # HTTP client, policy, idempotency
  dashboard/manifest.json          # {"name":"hermagotchi","api":"plugin_api.py"}
  dashboard/plugin_api.py          # FastAPI APIRouter; ctx.rest bridge
  desktop/plugin.js                # uncompiled ESM; only @hermes/plugin-sdk, react, react/jsx-runtime
  desktop/src/                     # UI + renderer sources (build → plugin.js)
  assets/manifest.json             # rig + species + items
  assets/species/ assets/items/
  art/source/ art/prompts/ art/PROVENANCE.md art/STYLE_GUIDE.md
  server/app/                      # FastAPI hosted game API
  server/tests/
  shared/schema/                   # JSON Schema + fixtures
  scripts/asset_validate.py
  scripts/render_contact_sheet.py
  scripts/pack_desktop_assets.mjs
  evals/measure_schemas.py         # o200k_base / cl100k_base token counts
  tests/                           # plugin contract + smoke
  docs/
```

**Integration branch:** `feat/hackathon` (never `main` from bees).  
**Launcher project key (planned):** `hermagotchi` → PC fixture path + `sync_branch: feat/hackathon`.

---

## 2. Agent tool catalog (exactly 8 composable tools)

NEVER add a 9th top-level tool. New behaviour = new `op` on an existing tool (EOH/shortrizz pattern). Declare the same 8 names in `plugin.yaml` `provides_tools`.

| Tool | Ops (enum) | Mutating? |
|---|---|---|
| `hermagotchi_status` | `me`, `pet`, `wallet`, `goal`, `inbox`, `health` | no |
| `hermagotchi_pet` | `adopt`, `rename`, `set_mode`, `care` (`feed`\|`play`\|`rest`) | yes (except reads via status) |
| `hermagotchi_goals` | `list`, `set`, `clear` | set/clear yes |
| `hermagotchi_challenge` | `list_opponents`, `invite`, `respond` (`accept`\|`decline`), `submit_tactics` | yes |
| `hermagotchi_battle` | `practice`, `get`, `replay`, `claim` | practice/claim yes |
| `hermagotchi_shop` | `catalog`, `inventory`, `buy`, `equip` | buy/equip yes |
| `hermagotchi_social` | `read`, `send`, `block`, `report` | send/block/report yes |
| `hermagotchi_meta` | `leaderboard`, `bounties`, `claim_bounty` | claim_bounty yes |

**Envelope (all tools):** return `{ok: bool, data: object|null, error_code: string|null, correlation_id: string}`. No HTML, no executable instructions, no secrets.

**Hard rules for bees:**
- Every mutation carries `idempotency_key` (client ULID/UUID) + owner policy check.
- Default policy: human mode, network off, autonomy off, chat off (see SPEC §3).
- LLM may choose among allowlisted moves/ops only; never submit code, expressions, or URLs as assets.
- Report o200k schema token delta via `python3 evals/measure_schemas.py` (tiktoken).

**Mapped from SPEC names:** `hermagotchi_adopt`/`care` → `hermagotchi_pet`; `hermagotchi_leaderboard` + bounties → `hermagotchi_meta`. Keep SKILL.md aliases documented; schemas expose only the 8 tools.

---

## 3. Server HTTP API (`/v1`)

Auth: every mutation authenticated; device-pairing preferred (SPEC §7 identity gate). Timestamps ISO-8601 UTC. Errors: `{code, message, retry_after_s, correlation_id}`.

| Method | Route | Purpose |
|---|---|---|
| POST | `/auth/pair/start` | device-link challenge |
| POST | `/auth/pair/complete` | scoped session |
| GET | `/healthz` | readiness only |
| GET | `/me` | account + permissions |
| POST | `/pets` | adopt once; server seeds appearance |
| GET | `/pets/{id}` | public sanitized pet |
| POST | `/pets/{id}/care` | feed/play/rest (idempotent) |
| GET | `/catalog` | versioned item catalog |
| GET | `/wallet` | balance projection |
| GET | `/ledger` | paginated history |
| POST | `/shop/purchases` | atomic debit + grant |
| POST | `/pets/{id}/equip` | ownership + compatibility |
| GET | `/bounties` | active tasks |
| POST | `/bounties/{id}/claim` | one-time award |
| POST | `/challenges` | invite |
| POST | `/challenges/{id}/respond` | accept/decline |
| POST | `/matches/{id}/tactics` | one tactic card |
| GET | `/matches/{id}` | status + replay |
| GET | `/leaderboard` | ranked slice |
| GET/POST | `/chat/channels/{id}/messages` | moderated chat |
| POST | `/moderation/report` | abuse report |

Optional later: polling cursor / `GET /events` envelope `{event_id, seq, type, version, occurred_at, data}`.

**Local gateway:** `dashboard/plugin_api.py` exposes thin proxies under `/api/plugins/hermagotchi/*` via `ctx.rest`. Desktop never holds long-lived secrets.

---

## 4. DB schema (logical)

SQLite OK for unit/local single-process tests; PostgreSQL required for multi-worker production ledgers.

```
accounts(id, public_handle, status, created_at, privacy_flags)
devices(id, account_id, public_key, revoked_at, created_at)
pets(id, account_id, species, appearance_seed, traits_json, level, xp,
     stats_json, care_json, care_updated_at, created_at, revision)
wallets(account_id PRIMARY KEY, balance, revision)
ledger(id, account_id, delta, reason, source_event_id UNIQUE, created_at)
items(id, slot, rarity, price_bits, asset_id, compatible_rigs_json,
      catalog_version, active)
inventory(account_id, item_id, acquired_at, source_event_id, UNIQUE(account_id,item_id))
equipment(pet_id, slot, item_id, equipped_at, UNIQUE(pet_id,slot))
challenges(id, challenger_id, defender_id, mode, status, expires_at, created_at)
matches(id, challenge_id UNIQUE, ruleset_version, economy_version,
        seed_commitment, seed, status, replay_hash, resolved_at)
tactics(match_id, account_id, card_json, locked_at, UNIQUE(match_id,account_id))
match_events(id, match_id, seq, event_json, UNIQUE(match_id,seq))
reward_entitlements(id, match_id, account_id, kind, awarded_at,
                    UNIQUE(match_id,account_id,kind))
bounties(id, starts_at, expires_at, rule_json, reward_json)
bounty_claims(account_id, bounty_id, claimed_at, UNIQUE(account_id,bounty_id))
ratings(account_id, season_id, rating, wins, losses, UNIQUE(account_id,season_id))
chats(id, channel_id, account_id, actor_mode, body, created_at, deleted_at)
blocks(blocker_id, blocked_id, created_at, UNIQUE(blocker_id,blocked_id))
moderation_reports(id, reporter_id, target_type, target_id, reason, status)
```

**Invariant:** `wallets.balance = sum(ledger.delta)` for that account. Currency/reward rows use one ACID transaction (`SELECT … FOR UPDATE` or equivalent).

---

## 5. Combat ruleset (`battle-1`)

- **Format:** async tactic cards; 1v1; 100 base HP; six-round cap; modes: `practice` | `casual` | `ranked`.
- **Species (v1):** `byteblob`, `patchfox`, `nullgeist` — distinct silhouettes; appearance never modifies ranked damage.
- **Tactic card:**
  ```json
  {
    "ruleset_version": "battle-1",
    "stance": "aggressive|balanced|defensive|control",
    "actions": [
      {"when": {"self_hp_lte_pct": 30}, "move": "guard"},
      {"when": {"special_ready": true}, "move": "glitch_pulse"},
      {"when": {"opponent_guarding": true}, "move": "focus"},
      {"when": {"always": true}, "move": "basic_attack"}
    ],
    "emote_id": "emote.sparkle"
  }
  ```
  Max 4 actions; unknown moves/predicates → reject with code; missing/invalid → neutral default.
- **Pure engine:** `resolve_match(ruleset, pet_a, pet_b, tactics_a, tactics_b, seed) -> Replay`. Caller never supplies winner, damage, or rewards.
- **Example damage:** `max(1, move_power + 2 * attacker.attack - defender.guard)`; guard reduces incoming by fixed % from versioned constants file.
- **Replay event:** `{round, actor, move, hp_before, hp_after, status_delta, result, rng_counter}` + `ruleset_version` + SHA-256 of canonical events.
- **Rating (ranked only):** Elo-like start 1000; K=24 provisional, K=16 established; floor 0. Practice never changes rating.
- **Timeouts:** published deadlines; no payout for never-played/expired invites.

---

## 6. Ledger / idempotency / economy

| Trigger | Bits (hypotheses) | XP | Notes |
|---|---:|---:|---|
| First casual PvP / UTC day | 50 | 30 | once |
| Win casual | 80 | 50 | |
| Lose casual | 20 | 30 | |
| Win ranked | 100 | 60 | |
| Lose ranked | 25 | 35 | |
| Practice bot | 10 | 15 | max 3/day |
| Daily bounty | 100–250 | 20–50 | one claim |

- Daily earn cap **800 Bits**/account (excl. one-off achievements).
- Max 3 rewarded matches vs same opponent/day; anti-farm: diminishing/no reward for collusive repeats.
- Item prices: common 150, uncommon 350, rare 700, epic 1200, legendary 2000.
- **Purchase:** `POST /shop/purchases` with `idempotency_key` — atomic debit + inventory grant exactly once, or neither.
- **Rewards:** unique `reward_entitlements(match_id, account_id, kind)`; retries return same receipt.
- Header/field: `Idempotency-Key` / `idempotency_key` required on all mutations.
- No negative wallet; no client-invented bounty; no real-money / transfers / wagers.

---

## 7. Asset manifest / rig schema

**Canvas:** 512×512 RGBA PNG; baseline `y=448`; centerline `x=256`; safe silhouette `x=65..447`, `y=75..450`.

**Rig family:** `small_front_v1` with species anchor overrides.

**Slots / z-order:**
`aura_back(-30), shadow(-20), back(-10), body(0), markings(5), eyes_mouth(10), face(20), head(30), front(40), particles_front(50)`.

**Equipped slots:** `head`, `face`, `back`, `front`, `aura`, `emote`, `habitat`, `title` (1 item/slot).

**Manifest shape (normative fields):**
```json
{
  "schema_version": 1,
  "asset_pack_id": "launch-001",
  "canvas": {"width": 512, "height": 512, "baseline_y": 448},
  "rigs": {
    "small_front_v1": {
      "anchors": {
        "head": [0.50, 0.23], "face": [0.50, 0.42],
        "back": [0.50, 0.47], "front": [0.50, 0.66], "ground": [0.50, 0.88]
      }
    }
  },
  "species": {
    "byteblob": {"rig": "small_front_v1", "base": "species/byteblob/body.png", "overrides": {}, "features": {}},
    "patchfox": {"rig": "small_front_v1", "base": "species/patchfox/body.png", "overrides": {"head": [0.50, 0.17]}, "features": {}},
    "nullgeist": {"rig": "small_front_v1", "base": "species/nullgeist/body.png", "overrides": {}, "features": {}}
  },
  "assets": [
    {
      "id": "hat.binary_crown", "slot": "head", "path": "items/binary_crown.png",
      "rig_families": ["small_front_v1"], "z": 30, "anchor": "head",
      "offset_px": [0, -4], "scale": 1.0, "sha256": "<computed>"
    }
  ]
}
```

**Validator (`scripts/asset_validate.py`) must check:** RGBA dims, non-empty alpha, path exists, unique ids, valid slot/z/anchor, sha256 matches file bytes, pack size budget, no off-canvas overflow metadata.

**Renderer:** pure `render_pet({species, appearance_seed, traits, palettes, loadout, pose, pack_version})` — deterministic; allowlisted asset IDs only; missing art → explicit broken indicator in dev.

**Art generation:** build-time only. **Provider/cost is a Kyle decision** — do not assume Nous/FAL/OpenAI access. Until authorized, bees may ship manifest schema + validator + placeholder *non-release* fixtures labeled `PLACEHOLDER_NOT_SHIP`; never present placeholders as final art.

**Desktop packaging:** embed size-bounded data-URIs or gateway asset route; package copy <64MB; no unsupported imports/JSX in disk `plugin.js`.

---

## 8. Shared JSON Schema files (integrator freeze targets)

Under `shared/schema/` (wave-1 contracts bee creates fixtures):

`PetPublic`, `PetPrivate`, `Appearance`, `Item`, `Wallet`, `LedgerEntry`, `Challenge`, `TacticCard`, `Match`, `ReplayEvent`, `ChatMessage`, `Goal`, `Policy`, `ApiError`, `GameEvent`, `AssetManifest`.

Version key: `contracts-v1`. Economy version: `economy-1`. Ruleset: `battle-1`. Asset pack: `launch-001` (when real art exists).

---

## 9. Security / catalog non-negotiables

- No core Hermes patches; no remote script injection; no reading `.env`/auth files/keychain.
- Secrets only via documented Hermes secret paths (`requires_env` / `agent.secret_scope.get_secret`).
- Game server never receives Hermes prompts, tool I/O, memory, or inference keys.
- Chat/opponent text is untrusted data; never enters governing prompts.
- `hermes plugins doctor` + `hermes plugins validate <path> --install-deps` before submission.
- Disclose hosted service operator/URL/data/retention in README.

---

## 10. Test commands (repo-wide)

```
python3 -m pytest -q tests
python3 -m pytest -q server/tests
python3 evals/measure_schemas.py
python3 scripts/asset_validate.py assets/manifest.json
```

Bees: test-first on assigned files; leave changes **uncommitted** in the sandbox (launcher collects `git diff HEAD`).

---

## Auth (contracts-v1 addendum)

`HERMAGOTCHI_AUTH_MODE=dev|production` (default `dev`; the VPS must set
`production`). Production ignores `X-Account-Id` completely and accepts only
`Authorization: Bearer <access_token>` resolved against the sessions table. Dev
tries the session token first, then falls back to the existing UUID stub.

Tokens are 256-bit URL-safe secrets with prefixes `hga_` (access), `hgr_`
(refresh), `hgd_` (device code). Only SHA-256 hex digests are stored. User codes
are 8 characters from `BCDFGHJKLMNPQRSTVWXZ23456789`, displayed `XXXX-XXXX`, and
normalized by uppercasing and removing `-`/spaces. Default TTLs: pairing 600 s,
access 3600 s, refresh 30 days; poll interval 5 s.

All endpoints are under `/v1`, return JSON, and use the standard error envelope
`{code, message, retry_after_s, correlation_id}`.

| Method | Path | Auth | Result |
|---|---|---|---|
| POST | `/v1/auth/pair/start` | none | `201 {"device_code","user_code","expires_at","interval_s":5,"new_account"}` |
| POST | `/v1/auth/pair/approve` | Bearer session (dev UUID stub allowed in dev) | `200 {"approved":true,"device_name"}` |
| POST | `/v1/auth/pair/token` | none | `200 {"access_token","refresh_token","token_type":"Bearer","expires_in","refresh_expires_in","account_id","device_id"}` |
| POST | `/v1/auth/refresh` | none | same token shape; rotates both tokens |
| GET | `/v1/auth/devices` | Bearer | `{"devices":[{"device_id","device_name","created_at","last_seen_at","current","revoked"}]}` |
| POST | `/v1/auth/devices/{device_id}/revoke` | Bearer | `{"revoked":true}` |
| POST | `/v1/auth/logout` | Bearer | revokes the current device |

Pair start body: `{"device_name": str<=64, "new_account": bool=false,
"public_handle": str<=32 optional}`. `new_account=true` auto-approves the first
device and token exchange creates a fresh account; `new_account=false` requires
an already-paired device to approve the user code. Approve body: `{"user_code"}`;
unknown/wrong → `404 invalid_user_code`, expired → `400 expired_token`, already
used → `409 already_used`. Token errors: `400 authorization_pending`,
`400 expired_token`, `400 invalid_grant` (unknown, already exchanged, or replay),
`429 slow_down`. Refresh reuse of an old token → `401 invalid_grant` and revokes
the device. Cross-account device revoke → `404`.

Limits are in-process: pair/start 10/minute/IP; five failed approvals lock the
user code/attempt source; polling faster than the interval returns `429` with
`retry_after_s`.
