# Hermagotchi — 90-second demo storyboard

**Prepared:** 2026-11-06  
**Target length:** under 90 seconds (hard cut, no slow waits)  
**Source:** DEVPLAN.md §K, adapted to the current release-candidate status.

This is a capture plan, not a promise that every feature is already hosted.
Record only what the build actually does. If a step cannot be shown honestly,
cut it or label it as practice/local and move on.

## Current status before recording

- **Hosted backend:** OPEN and **not deployed**. There is no public operator,
  endpoint or production account. The hosted target is an open decision for Kyle.
- **Local path:** `scripts/demo_local.sh` starts the FastAPI service on
  `127.0.0.1` only with a development auth stub and one seeded demo account.
- **Art:** placeholder/default-pipeline art may still be partial. Do not call a
  placeholder pack final, and do not claim a cosmetic is original production art
  unless the art provenance record supports it.
- **PvP:** a real two-owner ranked match requires two real authenticated
  accounts against the same backend. If that is not available, show a practice
  battle and label it **practice** on screen. Never describe a bot or
  pre-scripted response as real PvP.
- **Catalog:** the catalog YAML is an in-repo draft. No PR has been opened and no
  acceptance has been granted.

## Storyboard

| Clock | Action | Honest visual proof |
|---|---|---|
| 00:00-00:10 | Start Hermes Desktop with the plugin enabled. Show the status pane and one adopted pet. | Native pane, mode badge, and a distinct pet. If the art pack is partial, say "current placeholder art" in the voiceover or caption. |
| 00:10-00:21 | Open the agent goal "Save for Binary Crown" and show the active bounty. | Goal progress, wallet balance and settings; no invented numbers. |
| 00:21-00:32 | Hermes selects a valid tactic card and either sends a real challenge to a second authenticated account or starts a clearly labeled practice battle. | Tool trace plus challenge/match ID. If two real accounts are unavailable, the caption must read **practice — not PvP**. |
| 00:32-00:52 | Resolve the deterministic battle and show the replay. | Ruleset version, match ID, replay hash and round events from the server. Do not edit the outcome. |
| 00:52-01:01 | Show wallet/XP and the reward receipt. If a ranked match was played, show rating movement; if practice, show that rating did **not** change. | Ledger receipt and rating state. Practice and ranked must be visibly distinguished. |
| 01:01-01:13 | Buy and equip one cosmetic, then show the change on the pet. | Shop receipt, inventory entry and the equipped slot before/after. |
| 01:13-01:22 | Send one permitted chat line only if chat is explicitly enabled; otherwise show the safe disabled state. | Chat opt-in badge, moderation notice or the disabled control. Never show an unapproved chat flow. |
| 01:22-01:29 | End on the pet loadout, the eight tool names and the install command. | Hook, creativity and a clear local install path. No claim of a hosted service. |
| 01:29-01:30 | Title card: repo URL, branch `feat/hackathon`, catalog status "draft, PR not opened". | Accurate submission state. |

## Recording rules

1. Pre-capture allowed only if the underlying events are real. Never fake API
   responses, wallet values, ratings, match IDs or chat.
2. Keep the whole clip under 90 seconds. Cut loading and polling waits.
3. Label **practice** vs **ranked** on screen. Practice never changes rating.
4. Label any placeholder or partial art. Do not imply placeholder assets are the
   final generated art pack.
5. Redact secrets, tokens, private hosts, tailnet names and personal paths. Show
   only opaque IDs that are safe to publish.
6. State that the hosted service is **OPEN / not deployed** when the clip implies
   multiplayer. A local two-account run is still local.
7. Do not show a catalog PR, hosted dashboard or acceptance badge unless those
   artifacts actually exist at capture time.

## Reproducible local capture

```bash
# From the repository root, with the dev dependencies installed.
bash scripts/demo_local.sh
```

The script installs `requirements-dev.txt`, binds only to `127.0.0.1`, prints the
`/v1/healthz` and `POST /v1/pets` steps, and cleans up its temporary database.
It does not deploy anything and does not require real API keys.

For a two-account local PvP capture, use two seeded dev UUIDs against the same
local database and keep the caption explicit that this is a local development
auth path, not the production device-pairing flow.

## Post-production checklist

- [ ] Clip is under 90 seconds.
- [ ] Every match, wallet and rating value came from the running app.
- [ ] Practice and ranked are labeled.
- [ ] Placeholder/partial art is labeled.
- [ ] Hosted status is described as OPEN and not deployed.
- [ ] No secrets, private hosts or personal paths are visible.
- [ ] Repo URL and branch are correct.
