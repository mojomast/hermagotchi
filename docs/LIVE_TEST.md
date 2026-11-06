# Live API test — 2026-11-06 (America/Toronto)

Target: `https://api.hermagotchi.rizz.click` at tip `e6398c0` / prior deploy pin `12b0217`.
Auth mode: production. Signup cap 100 / 5 per IP. Proxy gate removed.

Tooling: `scripts/live_smoke.py` (reads `HERMAGOTCHI_API_BASE_URL`, stores sessions under `HERMES_PLUGIN_DATA_DIR`, mode `0600`).

## Actors

| Actor | Host | Species | Account id | Pet id | Notes |
|---|---|---|---|---|---|
| box-1 | box | firewyrm | `83b26779-8d44-4d12-ba50-311333d829d9` | `22b59c8e-e80e-4360-85d9-27882ee180a0` | Session later revoked by refresh-reuse probe |
| box-2 (peer stand-in) | box | patchfox | `41d0e021-e2a7-4bdc-8e2d-bec6c5f8a05f` | `7ebe33e3-3cdc-455f-90e9-a8a011425fe1` | Same public IP as box-1 |
| box-3 | box | daemowl | `2bcd4e09-64aa-4a2a-92a7-fd35323c234a` | (adopted in bootstrap) | Used for lockout + live UI shots |

**moltussy-1:** unreachable for this run. `tailscale status` shows the peer online, but Tailscale SSH host-key / pubkey auth failed (`Permission denied (publickey)` / host key strict checking). No changes were made on moltussy. Second account therefore ran on the box (same client IP). Different-IP signup_per_ip isolation was **not** re-verified live.

Session files (paths only, mode 0600): under `/tmp/hermagotchi-live-sessions/{box,peer,acct3}/`.

## Checklist

| Check | Result | Evidence |
|---|---|---|
| Pair new account (device pairing client) | **pass** | 3 accounts created via `PairingClient.start(new_account=True)` + `poll_token` |
| Adopt non-Byteblob | **pass** | firewyrm / patchfox / daemowl |
| Care feed/play/rest | **pass** | all 200/201 |
| GET `/me` | **pass** | returns `pet_id` |
| Catalog (81 items) | **pass** | |
| Buy + equip cheap cosmetic | **pass** (after PvP bits) | Initial buy failed `409 insufficient_funds` (starter Bits after 1 practice = 10; cheapest item = 150). After casual PvP, buy `hat.git_bandana` / `face.hex_specs` succeeded |
| Practice vs Teknium | **pass** | winners `a`; type multipliers present in events (e.g. firewall STAB) |
| PvP casual ×3 (both directions) | **pass** | see battle table |
| Leaderboard updates | **partial / bug** | XP on pets increased (firewyrm xp=185) but `/leaderboard` `total=0`, `me=null` after casual matches |
| Chat | **skip** | `GET /chat/messages` → 404 |
| Refresh-token rotation | **pass** | new access+refresh; old refresh → 401 |
| Old refresh reuse | **pass (by design)** | reusing rotated refresh revokes the device; subsequent `/me` → 401 |
| `X-Account-Id` only | **pass** | 401 `unauthorized` |
| Bad approve code lockout (5) | **pass with caveat** | Eventually `429 rate_limited`, but often needs >5 attempts (observed lock at attempt 15) — in-memory limiter + multiple uvicorn workers |
| Extra device approve + revoke | **pass** | device count 2 → revoke `200`; 1 active remains |
| Live UI shots | **pass** | `/workspace/hermagotchi-ui-shots/live/` |

## Battles

Challenger is side `a`, defender side `b`. Winner from `GET /matches/{id}` → `replay.winner` (match row itself omits winner — see bugs).

| # | Direction | Match id | Winner | Result | Rounds | Notable |
|---|---|---|---|---|---|---|
| 1 | firewyrm → patchfox | `bed5772a-c0a4-4373-a4e5-a791acd01639` | **a** | ko | 5 | b opens with `basic_attack` (17 dmg); final HP a=49 b=0 |
| 2 | patchfox → firewyrm | `5df148b6-eda3-423a-9743-74d83f649a2e` | **a** | ko | 6 | a `glitch_pulse` 25 dmg open; final HP a=20 b=0 |
| 3 | firewyrm → patchfox | `130754ad-441b-4ac3-a0aa-c6f864eaa7ee` | **b** | ko | 6 | b `glitch_pulse` 25; final HP a=0 b=20 |
| P | firewyrm practice | `ed914761-1232-4143-9200-8af1227d806e` | **a** | — | 6 | type_multiplier / stab_multiplier present on pulse |

## Bugs / open items

1. **Starter economy vs shop floor:** new accounts earn 10 Bits per rewarded practice (max 3/day) but cheapest catalog price is 150 → cannot buy any cosmetic until PvP (or another Bits source). Proposed: grant a small starter wallet on signup, or add a free/emote unlock, or lower a common item to ≤30.
2. **Match payload omits winner/result:** `GET /matches/{id}` returns `match` without `winner`/`result`/`final_hp`; those live only under `replay`. Desktop battle UI may look empty. Proposed: mirror `replay.winner`, `replay.result`, `replay.final_hp` onto the match projection (schema + route).
3. **Leaderboard empty after casual PvP:** pet XP updates, but season leaderboard stays empty. Casual may not write `ratings` (by design for ranked-only) — if casual should appear, seed/update ratings on casual resolve; otherwise document that leaderboard is ranked-only.
4. **Approve lockout across workers:** `AuthRateLimiter` is in-process; with multiple uvicorn workers, 5 failures may not lock until the same worker is hit repeatedly. Proposed: persist approve failure counts in SQLite (like signup_ip_stats) or use a shared Redis/limiter; or run approve route sticky.
5. **moltussy live second-IP path blocked:** no SSH pubkey / Tailscale SSH for this bot identity. Needs Kyle to allow the box key or enable Tailscale SSH for the grokbot user.
6. **Chat route 404** on live — confirm whether chat is disabled or path differs (`/v1/chat/...`).

## Screenshots

- `/workspace/hermagotchi-ui-shots/live/01-habitat.png`
- `/workspace/hermagotchi-ui-shots/live/02-battle.png`
- `/workspace/hermagotchi-ui-shots/live/03-shop.png`

## Reproduce

```bash
git checkout e6398c0   # or current feat/hackathon
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export HERMAGOTCHI_API_BASE_URL=https://api.hermagotchi.rizz.click/v1
export HERMES_PLUGIN_DATA_DIR=/tmp/hg-live-a
python3 scripts/live_smoke.py --data-dir "$HERMES_PLUGIN_DATA_DIR" --report /tmp/a.json bootstrap --species firewyrm
# … challenge / accept / tactics / auth-checks subcommands
```


---

# Live API test — W11 post-deploy — 2026-11-06 ~03:10 America/Toronto

Target: `https://api.hermagotchi.rizz.click` at deployed SHA `1fec02f8c518a5b2e59371be6c2f9e24ac32ebc0` (rollback `12b0217`). Migration `0011_starter_and_rate_limits` applied on VPS.

Actors (existing sessions only; no new accounts):

| Actor | Host | Species | Account id | Pet id |
|---|---|---|---|---|
| box-fw | box | firewyrm | `56c72059-ae46-4d71-8f6f-a4b87c2fc473` | `7273c432-3542-4617-af78-f53f70cc0bc7` |
| moltussy01 | moltussy-1 | patchfox | `6a4d7385-2d7f-410b-a676-de9f5b5db2f6` | `f77bfe6e-ca20-417b-8970-a8154b0b068a` |
| acct3 (wallet spot-check) | box | daemowl | `2bcd4e09-64aa-4a2a-92a7-fd35323c234a` | `70405183-570a-4e5d-b659-2eec5bc0d020` |

Sessions: `/tmp/hermagotchi-live-sessions/{box-fw,acct3}/` and `~/hermagotchi-livetest/session` on moltussy-1. Peer session (`41d0e021-…`) refresh returned `invalid_grant` — unused.

## Checklist

| Check | Result | Evidence |
|---|---|---|
| Starter Bits grant (~300) | **PASS** | Ledger `economy.starter_grant` amount 300 on box-fw, acct3, and moltussy01. Balances before this run reflected the grant (e.g. acct3=310 = 300+old practice 10). |
| Practice pays 50 Bits | **PASS** | box-fw practice match `6f8b750e-0b84-48e0-af88-8ac71c606323`; wallet 590→640 (Δ+50); ledger `battle.practice.bits` 50. |
| Buy + equip cheap shop item | **PASS** | Bought `aura.leaf_orbit` (150 Bits) → 201; equip → 200; pet `equipment.aura=aura.leaf_orbit` / loadout shows item. |
| Casual PvP ×2 match fields | **PASS** | Matches `da2aa0a7-…` and `768946e8-…`; each `match` includes `winner`, `result`, `final_hp`, `rounds` (both winner=`a`, result=`ko`, final_hp={a:49,b:0}, rounds=5). |
| Leaderboard after casual | **PASS** | `/v1/leaderboard` total=2; firewyrm rank 1 rating 1023 (W2/L0); moltussy01 patchfox rank 2 rating 977 (W0/L2). |
| Lobby chat post+read | **PASS** | POST `/v1/chat/channels/lobby/messages` 201 from both sides (msg ids `7e1d9acf-…`, `6352187c-…`); GET returns both "live test 🐾 …" messages. |
| Wrong-approve lockout | **SKIP** | Deliberately not run against real IP (per brief). |

## Battles (W11)

| # | Direction | Match id | Winner | Result | Rounds | final_hp |
|---|---|---|---|---|---|---|
| 1 | firewyrm → moltussy01 | `da2aa0a7-5752-4b3f-9662-a64eaca8fe87` | a | ko | 5 | a=49 b=0 |
| 2 | firewyrm → moltussy01 | `768946e8-ec67-419e-a528-68f163222be2` | a | ko | 5 | a=49 b=0 |

## W11 bugs previously open — live status

1. Starter economy — **fixed live** (300 Bits grant present).
2. Match payload winner/result/final_hp/rounds — **fixed live** (on `match`, not only replay).
3. Leaderboard empty after casual — **fixed live** (casual updates ratings).
4. Approve lockout across workers — **not re-tested live** (skipped).
5. moltussy SSH — **works** this run (`ssh clanker01@moltussy-1`).
6. Chat route 404 — **fixed live** (correct path `/v1/chat/channels/lobby/messages`).

## Notes

- Peer account session is stale (`invalid_grant` on refresh); did not recreate.
- No VPS changes, no Hermes plugin changes on moltussy-1, no new accounts.
