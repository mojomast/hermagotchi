# Hermagotchi

Hermes Agent plugin: a co-op virtual-pet game with deterministic async battles,
earned Bits, goals, cosmetic unlocks, leaderboards and moderated social play.
Exactly **8 composable tools** are exposed; new behaviour is always a new `op`
on an existing tool, never a ninth tool.

**Hackathon deadline:** 2026-11-11 5:00 PM ET  
**Integration branch:** `feat/hackathon` (never `main`)  
**Status:** release candidate on `feat/hackathon`. It is **not tagged** and is
**not on `main`**. Hosted deployment is **optional and OPEN** for the operator;
the plugin remains local-first and network-off by default.

## Current build

| Area | Current state |
|---|---|
| Asset pack / runtime catalog | `launch-003` (`ASSET_PACK_VERSION`) |
| Adoptable species | **10**, all with launch-003 pixel art: Byteblob, Patchfox, Nullgeist, Kernelcrab, Cachebat, Stacktoise, Daemowl, Shellsnail, Regexopus, Firewyrm |
| Shop | **81** active cosmetic items across head, face, back, front, aura, emote, habitat and title slots |
| Desktop | Six-tab pane; launch-003 per-species compose anchors for every cosmetic |
| Auth | Device pairing with short-lived user codes; `HERMAGOTCHI_AUTH_MODE` defaults to `dev` |

## Tools

| Tool | Purpose |
|---|---|
| `hermagotchi_status` | account, pet, wallet, goal, inbox and health reads |
| `hermagotchi_pet` | adopt, rename, set mode and care actions |
| `hermagotchi_goals` | list, set and clear agent/human goals |
| `hermagotchi_challenge` | opponents, invites, responses and tactics |
| `hermagotchi_battle` | practice, match reads, replay and reward claim |
| `hermagotchi_shop` | catalog, inventory, buy and equip |
| `hermagotchi_social` | moderated read/send plus block and report |
| `hermagotchi_meta` | leaderboard, bounties and bounty claims |

All tools return the contracts-v1 envelope:
`{ok, data, error_code, correlation_id}`. Mutations require an idempotency key
and pass the local policy gate.

## Install from source

`plugin.yaml` declares `requires_hermes: ">=0.21.0"`. From a checkout of the
integration branch:

```bash
git clone https://github.com/mojomast/hermagotchi.git
cd hermagotchi
git checkout feat/hackathon
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
```

Register and validate the plugin against your local Hermes install:

```bash
hermes plugins doctor .
hermes plugins validate . --install-deps
```

Then enable the plugin explicitly. Network access, agent autonomy and agent
chat are separate opt-ins and stay disabled until the operator turns them on.

## Auth and server defaults

The server and client implement device pairing: `POST /v1/auth/pair/start`,
`approve` and `token` issue short-lived user codes, and only SHA-256 token
digests are stored. The client stores its session with owner-only permissions,
supports refresh and device revoke, and never prints raw tokens.

- `HERMAGOTCHI_AUTH_MODE` defaults to **`dev`**. Set it to **`production`** on a
  hosted deployment; production ignores `X-Account-Id` and accepts only a valid
  session access token.
- `HERMAGOTCHI_SIGNUP_CAP` (default `100`) caps total accounts.
- `HERMAGOTCHI_SIGNUP_PER_IP` (default `5`) caps lifetime accounts per client IP.
- Signup failures return HTTP `403` with `signup_closed` or `signup_ip_limit`.
- `HERMAGOTCHI_TRUSTED_PROXY` (`1`, `true` or `yes`) enables the left-most
  `X-Forwarded-For` hop (falling back to `X-Real-IP`). Leave it unset unless a
  trusted reverse proxy sanitizes those headers.

See [`docs/AUTH.md`](./docs/AUTH.md) for the full pairing and signup contract.

## Desktop pane

The Desktop contribution exposes six tabs: **Habitat**, **Battle**, **Shop**,
**Leaderboard**, **Chat** and **Settings**. It renders explicit
backend-disabled, network-off, auth-missing and service-unavailable states
instead of a blank pane, and keeps Chat off until the owner enables it. Pet art
is composed from the launch-003 manifest (32x32 native, nearest upscale) using
per-species `head`, `face`, `back`, `front`, `hand` and `ground` anchors, so
every cosmetic fits all ten species.

See [`docs/DESKTOP_UI.md`](./docs/DESKTOP_UI.md) for the pane contract and build
steps.

## Local demo

`scripts/demo_local.sh` starts the FastAPI service on `127.0.0.1` only, installs
the dev requirements, seeds one local demo account and prints/executes the
`healthz` and adopt steps. It never binds a public interface, never deploys and
never asks for a real API key.

```bash
bash scripts/demo_local.sh
```

See [`docs/DEMO.md`](./docs/DEMO.md) for the honest 90-second storyboard and
capture rules.

## Disclosures

| Area | Current status |
|---|---|
| Hosted service operator | **TBD / OPEN** — an optional operator decision; no public endpoint has been chosen. |
| Hosted target | **Hosted target not chosen — open decision for Kyle.** Hosted deployment is optional and nothing is deployed. |
| Network | Network is **off** by default (`permissions.network: false`, `network_enabled: false`). All network use requires explicit operator consent. |
| Chat retention | Chat is off by default. If enabled, message retention and moderation logs are **TBD** until the operator publishes a policy. |
| Permissions | Filesystem read only; no secret values are requested (`secrets: []`); no inbound ports are opened on player machines. |
| Limitations | Auth defaults to `dev` for local work; production must set `HERMAGOTCHI_AUTH_MODE=production` and use paired sessions. Practice battles never change rating; ranked/PvP requires real authenticated accounts and a hosted service. Files under `assets/fixtures/` are test-only placeholders and are not release art; the shipped launch-003 pack is the current game art. |
| Data deletion | No production service exists by default. Local data lives in the SQLite file you configure and can be deleted by removing that file. Any hosted account/data-deletion policy is **TBD** with the operator. |
| Cost | The plugin itself has no paid tier. Optional LLM inference or a hosted service may incur operator/user costs; none are enabled by default. |

Do not describe practice matches as player-versus-player, do not present fixture
placeholders as release art, and do not claim catalog acceptance or a live
hosted demo before either exists.

## Security and contracts

- [`docs/SECURITY.md`](./docs/SECURITY.md) — threat model, auth, secrets, reporting
- [`docs/CONTRACTS.md`](./docs/CONTRACTS.md) — frozen contracts-v1 (tools, API, combat, ledger, assets)
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — package and service layout
- [`docs/HANDOFF.md`](./docs/HANDOFF.md) — release SHA, checks, known gaps and manual submission checklist
- [`SPEC.md`](./SPEC.md) — product and technical specification
- [`DEVPLAN.md`](./DEVPLAN.md) — development plan and demo storyboard source
- [`ORCHESTRATOR_PROMPT.md`](./ORCHESTRATOR_PROMPT.md) — orchestrator kickoff

The in-repo catalog draft lives at
[`docs/catalog/hermagotchi.yaml`](./docs/catalog/hermagotchi.yaml). It mirrors
plugin version `0.1.0` and the eight tools; the runtime asset pack and shop
catalog report `launch-003`. The catalog is a draft only: **no catalog PR has
been opened** and the placeholder SHA must be replaced with the final
40-character commit SHA before submission.

## License

MIT. See [`LICENSE`](./LICENSE). Generated art rights are documented separately
by the art pipeline; fixture placeholders are not a release claim.
