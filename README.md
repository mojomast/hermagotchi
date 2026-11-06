# Hermagotchi

Hermes Agent plugin: a co-op virtual-pet game with deterministic async battles,
earned Bits, goals, cosmetic unlocks, leaderboards and moderated social play.
Exactly **8 composable tools** are exposed; new behaviour is always a new `op`
on an existing tool, never a ninth tool.

**Hackathon deadline:** 2026-11-11 5:00 PM ET  
**Integration branch:** `feat/hackathon` (never `main`)  
**Status:** release-candidate scaffolding. The hosted backend is **OPEN and not
deployed**; the plugin remains local-first and network-off by default.

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
| Hosted service operator | **TBD / OPEN** — no operator or public endpoint has been chosen. |
| Hosted target | **Hosted target not chosen — open decision for Kyle.** Nothing is deployed. |
| Network | Network is **off** by default (`permissions.network: false`, `network_enabled: false`). All network use requires explicit operator consent. |
| Chat retention | Chat is off by default. If enabled against a future hosted service, message retention and moderation logs are **TBD** until the operator publishes a policy. |
| Permissions | Filesystem read only; no secret values are requested (`secrets: []`); no inbound ports are opened on player machines. |
| Limitations | The repo may still contain placeholder or partial art packs; the local server uses a development auth stub; practice battles never change rating; ranked/PvP requires real authenticated accounts and is not demonstrated on a hosted service yet. |
| Data deletion | No production service exists. Local data lives in the SQLite file you configure and can be deleted by removing that file. Hosted account/data-deletion policy is **TBD** with the operator. |
| Cost | The plugin itself has no paid tier. Optional LLM inference or a future hosted service may incur operator/user costs; none are enabled by default. |

Do not describe practice matches as player-versus-player, do not present
placeholder art as final generated art, and do not claim catalog acceptance or
a live hosted demo before either exists.

## Security and contracts

- [`docs/SECURITY.md`](./docs/SECURITY.md) — threat model, auth, secrets, reporting
- [`docs/CONTRACTS.md`](./docs/CONTRACTS.md) — frozen contracts-v1 (tools, API, combat, ledger, assets)
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — package and service layout
- [`docs/HANDOFF.md`](./docs/HANDOFF.md) — release SHA, checks, known gaps and manual submission checklist
- [`SPEC.md`](./SPEC.md) — product and technical specification
- [`DEVPLAN.md`](./DEVPLAN.md) — development plan and demo storyboard source
- [`ORCHESTRATOR_PROMPT.md`](./ORCHESTRATOR_PROMPT.md) — orchestrator kickoff

The in-repo catalog draft lives at
[`docs/catalog/hermagotchi.yaml`](./docs/catalog/hermagotchi.yaml). It is a
draft only: **no catalog PR has been opened** and the placeholder SHA must be
replaced with the final 40-character commit SHA before submission.

## License

MIT. See [`LICENSE`](./LICENSE). Generated art rights are documented separately
by the art pipeline; placeholder assets are not a release claim.
