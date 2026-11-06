# Hermagotchi Desktop UI sources

These files are the developer-source UI for the native Hermes Desktop pane.
They are **not** the shipped `desktop/plugin.js`; the integrator owns packing the
final uncompiled ESM bundle. Sources use only `react`, `react/jsx-runtime` and
(optionally) `@hermes/plugin-sdk`, call `jsx()` / `jsxs()` directly, and contain
no JSX markup or extra npm dependencies.

## Tab map

| Tab | Module | Stub contents |
|---|---|---|
| Habitat | `tabs/HabitatTab.js` | Pet name/species placeholders, mode, XP/goal, Fullness/Happiness/Energy care meters |
| Battle | `tabs/BattleTab.js` | Challenge inbox placeholder, empty-state copy, disabled practice action |
| Shop | `tabs/ShopTab.js` | Bits balance placeholder, price table, preview-only note; purchase controls disabled (no spend) |
| Leaderboard | `tabs/LeaderboardTab.js` | Season/rank table header, empty ranked state, personal-neighborhood placeholder |
| Chat | `tabs/ChatTab.js` | Chat-off notice, disabled composer and mute/block/report actions |
| Settings | `tabs/SettingsTab.js` | Read-only backend, network, identity, chat, autonomy and service placeholders |

`pane.js` exports `TAB_IDS`, `TAB_LABELS`, `TAB_COMPONENTS` and the
`HermagotchiPane` component. `states.js` exports the shared setup/offline states
(`backend_disabled`, `network_off`, `auth_missing`, `service_unavailable`) plus
`resolveUiState()` and the `StateNotice` component.

## Integrator import

From the desktop bundle source, import the pane registration helper and call it
inside the plugin's `register(ctx)`:

```js
import {
  registerHermagotchiPane,
  createDesktopPlugin,
} from "./src/ui/index.js";

export function register(ctx) {
  return registerHermagotchiPane(ctx);
}

export default createDesktopPlugin();
```

The helper calls `ctx.register({ area: "panes", id: "hermagotchi", ... })` with a
React render function. If the installed SDK uses a different pane-registration
signature, use `createPaneContribution()` directly and pass the contribution in
the SDK-supported form.

When packing `desktop/plugin.js`, inline these modules (or bundle them without
dynamic imports/eval) and keep only the allowed import specifiers. Do not copy
this README or tests into the runtime bundle. The Desktop enable toggle is
separate from the Python backend toggle; the pane's state notice must reflect
both.

## Layout tests

```bash
python3 -m pytest -q tests/test_desktop_ui_layout.py
```

The test is filesystem-only: it checks required modules, exported symbol names,
the six-tab order, placeholder copy, allowed imports, no JSX tags, and that no
secret or private-machine paths leak into the sources or docs.
