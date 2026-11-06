# Hermagotchi Desktop UI

Status: the six-tab Desktop pane is live behind the host gates. The Chat tab is
wired through the local dashboard bridge and remains off until the owner enables
`chat_enabled`; the other tabs keep their deterministic placeholders. The
generated `desktop/plugin.js` is produced from `desktop/src/ui/` by the build
script and is safe to review as uncompiled ESM.

## Goals and constraints

- One native pane with tabs: **Habitat**, **Battle**, **Shop**, **Leaderboard**,
  **Chat**, **Settings**.
- Sources live under `desktop/src/ui/` and use the React runtime directly through
  `jsx()` / `jsxs()`. No JSX markup is stored in the sources that are packed as
  uncompiled ESM.
- Allowed imports only: `@hermes/plugin-sdk`, `react`, `react/jsx-runtime`, plus
  relative modules inside the UI source tree. No additional npm packages.
- Desktop JavaScript never holds or sees the session token. Every server call
  goes through the local dashboard bridge, which owns `Authorization: Bearer`
  handling and never returns tokens.
- Pure logic lives in `desktop/src/ui/logic/` and imports no React, so it can be
  tested with `node --test`.
- Every setup/offline condition is explicit rather than a blank pane.

## Module map

| Path | Responsibility |
|---|---|
| `desktop/src/ui/index.js` | Public re-export surface for the integrator |
| `desktop/src/ui/pane.js` | `HermagotchiPane`, tab order, labels and component map |
| `desktop/src/ui/states.js` | Shared state codes, copy, `resolveUiState()` and `StateNotice` |
| `desktop/src/ui/register.js` | `registerHermagotchiPane()`, pane contribution and desktop plugin factory |
| `desktop/src/ui/api.js` | Bridge client; the only UI module allowed to call `fetch` |
| `desktop/src/ui/styles.css` | Dark retro `hg-` stylesheet injected by the built plugin |
| `desktop/src/ui/components/CareMeter.js` | Accessible care-meter stub used by Habitat |
| `desktop/src/ui/components/NpcHostBanner.js` | Display-only NPC banner used by each tab |
| `desktop/src/ui/logic/chat.js` | Pure chat envelope, validation, merge and moderation helpers |
| `desktop/src/ui/tabs/HabitatTab.js` | Pet placeholders, care meters, XP/goal |
| `desktop/src/ui/tabs/BattleTab.js` | Challenge inbox placeholder |
| `desktop/src/ui/tabs/ShopTab.js` | Bits/price preview; disabled purchase controls |
| `desktop/src/ui/tabs/LeaderboardTab.js` | Ranked table header and empty state |
| `desktop/src/ui/tabs/ChatTab.js` | Live lobby behind `chat_enabled`; existing chat-off stub otherwise |
| `desktop/src/ui/tabs/SettingsTab.js` | Read-only settings placeholders |
| `scripts/build_desktop.mjs` | Zero-dependency bundler and `--check` staleness guard |

## Tab behavior

The pane keeps the active tab in component state and exposes an optional
`onTabChange` callback. The integrator may instead supply `initialTab={...}` and
control selection from the host.

- **Habitat** shows `Pet name`, `Species` and `Mode` placeholders plus the
  `Fullness`, `Happiness` and `Energy` care meters. No pet is adopted by this
  stub.
- **Battle** shows a `Challenge inbox` with `No pending challenges.` and a
  disabled practice action.
- **Shop** shows `Bits balance`, a `Price` table and preview-only copy. Every
  purchase button is disabled; the stub never spends Bits.
- **Leaderboard** shows the `Leaderboard` table with `Rank`, `Player`, `Rating`
  and `Record`, an empty `No ranked matches yet` row, and a neighborhood
  placeholder.
- **Chat** renders the existing `Chat is off by default` stub until chat is
  enabled. When enabled and an `api` prop is present, it reads
  `GET /chat/channels/lobby/messages`, sends through the bridge, and offers
  report/block actions. Every message body is rendered as plain text, never as
  HTML. Nous Girl hosts rejected/blocked notices via `npcHostLine`.
- **Settings** lists `Python backend`, `Multiplayer`, `Identity`, `Chat`,
  `Agent autonomy` and `Multiplayer URL` as read-only placeholders.

## Chat feature flag

The canonical server/policy key is `chat_enabled` (aliased as
`agent_chat_enabled` in the agent policy). It defaults to off. The Desktop tab
accepts `chatEnabled`, `chat_enabled`, `policy.chat_enabled` or
`status.policy.chat_enabled`; when the flag is absent or false it renders the
existing chat-off stub. Mutations still pass through bridge allowlisting and the
server's moderation, rate-limit and block checks.

## State model

`resolveUiState()` reports the first applicable condition in this order:

1. `backend_disabled` — Python backend is off.
2. `network_off` — owner policy has multiplayer disabled.
3. `auth_missing` — this device is not paired.
4. `service_unavailable` — the hosted service cannot be reached.
5. `ready` — all gates are open.

`StateNotice` renders the matching label, explanation and next-step hint. This
keeps disabled, unpaired and unreachable conditions distinguishable, as required
by the product acceptance criteria.

## Build

`desktop/plugin.js` is generated, not hand-edited. The bundler needs Node 22 and
zero npm packages: it inlines relative imports from `desktop/src/ui/index.js`,
keeps only `react`, `react/jsx-runtime` and `@hermes/plugin-sdk` as external
imports, and injects `styles.css` as a style tag when the plugin registers.

```bash
node scripts/build_desktop.mjs
node scripts/build_desktop.mjs --check
```

`--check` exits non-zero when `desktop/plugin.js` is stale. After rebuilding,
open Hermes Desktop and use **Plugins > Rescan** to pick up the new
`desktop/plugin.js`.

## Integrator handoff

1. Import `registerHermagotchiPane` (or `createPaneContribution`) from
   `desktop/src/ui/index.js` inside the source tree, or use the generated
   `desktop/plugin.js` default plugin.
2. Keep the pane id `hermagotchi`.
3. Rebuild with `node scripts/build_desktop.mjs` after changing any UI source or
   `styles.css`; never edit the bundle by hand.
4. Keep the Desktop pane toggle separate from the Python backend toggle, and
   pass the resulting gate state plus `chat_enabled` into `HermagotchiPane`.
5. Do not add credentials, token storage or host DOM overrides in the UI
   sources.

## Verification

```bash
node --test tests/js/
python3 -m pytest -q tests/test_desktop_ui_layout.py
python3 -m pytest -q tests server/tests
```

The Python layout test is filesystem-only. It verifies required files and
exports, the six-tab order, placeholder copy, allowed imports, absence of JSX
tags, `fetch` confined to `api.js`, and the absence of secret or
private-machine path patterns. JS tests cover chat logic, the bundle contents
and the stale-bundle guard without real network access.
