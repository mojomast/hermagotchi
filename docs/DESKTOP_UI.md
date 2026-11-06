# Hermagotchi Desktop UI (HGT-W3-I)

Status: source-level pane scaffold for integration into the integrator-owned
`desktop/plugin.js`. The six tab modules are stubs with deterministic
placeholders; no live game state, no network calls and no purchases are wired
here.

## Goals and constraints

- One native pane with tabs: **Habitat**, **Battle**, **Shop**, **Leaderboard**,
  **Chat**, **Settings**.
- Sources live under `desktop/src/ui/` and use the React runtime directly through
  `jsx()` / `jsxs()`. No JSX markup is stored in the sources that will later be
  packed as uncompiled ESM.
- Allowed imports only: `@hermes/plugin-sdk`, `react`, `react/jsx-runtime`, plus
  relative modules inside the UI source tree. No additional npm packages.
- `desktop/plugin.js` remains integrator-owned; this scaffold must not write or
  overwrite it.
- Every setup/offline condition is explicit rather than a blank pane.

## Module map

| Path | Responsibility |
|---|---|
| `desktop/src/ui/index.js` | Public re-export surface for the integrator |
| `desktop/src/ui/pane.js` | `HermagotchiPane`, tab order, labels and component map |
| `desktop/src/ui/states.js` | Shared state codes, copy, `resolveUiState()` and `StateNotice` |
| `desktop/src/ui/register.js` | `registerHermagotchiPane()`, pane contribution and desktop plugin factory |
| `desktop/src/ui/components/CareMeter.js` | Accessible care-meter stub used by Habitat |
| `desktop/src/ui/tabs/HabitatTab.js` | Pet placeholders, care meters, XP/goal |
| `desktop/src/ui/tabs/BattleTab.js` | Challenge inbox placeholder |
| `desktop/src/ui/tabs/ShopTab.js` | Bits/price preview; disabled purchase controls |
| `desktop/src/ui/tabs/LeaderboardTab.js` | Ranked table header and empty state |
| `desktop/src/ui/tabs/ChatTab.js` | Chat-off stub and disabled social actions |
| `desktop/src/ui/tabs/SettingsTab.js` | Read-only settings placeholders |

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
- **Chat** states `Chat is off by default` and disables the composer,
  send, mute, block and report controls.
- **Settings** lists `Python backend`, `Multiplayer`, `Identity`, `Chat`,
  `Agent autonomy` and `Multiplayer URL` as read-only placeholders.

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

## Integrator handoff

1. Import `registerHermagotchiPane` (or `createPaneContribution`) from
   `desktop/src/ui/index.js`.
2. Call it inside the plugin `register(ctx)` and keep the pane id
   `hermagotchi`.
3. Pack this source tree into the final `desktop/plugin.js` using the approved
   build path. Inline relative modules and preserve only the allowed import
   specifiers.
4. Keep the Desktop pane toggle separate from the Python backend toggle, and
   pass the resulting gate state into `HermagotchiPane`.
5. Do not add network calls, credentials or host DOM overrides in the UI
   sources.

## Verification

```bash
python3 -m pytest -q tests/test_desktop_ui_layout.py
```

The test is pure Python filesystem analysis. It verifies required files and
exports, the six-tab order, placeholder copy, allowed imports, absence of JSX
tags, and the absence of secret or private-machine path patterns.
