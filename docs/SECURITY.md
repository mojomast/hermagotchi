# HERMAGOTCHI — Security Model

**Status:** hardening baseline for `feat/hackathon` (contracts-v1)  
**Applies to:** the Hermes plugin entrypoint, the eight agent tools, the local
gateway, the desktop pane, and the optional hosted game API.

This document describes the security intent that the code and tests enforce. It
does not replace the frozen contracts in `docs/CONTRACTS.md`; where the two
overlap, the contracts and the tests are authoritative.

## 1. Scope and trust boundaries

Hermagotchi has three separate surfaces:

1. **Agent plugin** — `register(ctx)` declares one skill and exactly eight
   composable tools. Tools return a bounded envelope and never execute code
   supplied by a player, opponent, chat message, replay, or server response.
2. **Local gateway / desktop pane** — the desktop bundle is reviewable,
   uncompiled ESM. The desktop never holds long-lived service credentials.
3. **Optional hosted game API** — a separate FastAPI service with its own
   accounts, sessions, database, and operator.

The game service is not a prompt source, a memory store, or an inference proxy.
Hermes prompts, tool arguments/results, conversation history, memory, and model
provider keys stay outside the game boundary.

## 2. Authentication, authorization, and account isolation

- Every mutation requires an authenticated account session. The hosted API uses
  an OAuth-style device-pairing flow; the injectable UUID account-header stub is
  available only in `HERMAGOTCHI_AUTH_MODE=dev`.
- Server-side account identity is derived from the authenticated session, never
  from a client-supplied owner field. Extra body fields such as `account_id`,
  `balance`, `delta`, or `amount` are ignored for authorization and pricing.
- Wallet, ledger, inventory, goals, and blocks are account-scoped. Account B can
  never read or mutate account A's wallet, ledger, inventory, or equipment.
- A pet's public view is intentionally sanitized: owner id, appearance seed, and
  private care timestamps are removed. Private pet operations require ownership.
- Challenge responses are limited to the challenged account; match reads and
  tactic submissions are limited to match participants. Non-participants receive
  a denial, not a partial result.
- Every mutation carries a client-generated `idempotency_key`. Reusing a key
  returns the original receipt; a key is bound to one account and one operation
  and cannot be replayed into another account's state.

### Device pairing and session tokens

- `HERMAGOTCHI_AUTH_MODE` selects `dev` (default) or `production`. Production
  **must** be set on the VPS. In production `X-Account-Id` is ignored entirely;
  only `Authorization: Bearer <access_token>` resolved against the session table
  is accepted. Raw UUID bearer values are rejected. Dev tries the session token
  first and then falls back to the legacy UUID stub for local tests only.
- Approval model: the first device may self-register a fresh account with
  `new_account=true`. Additional devices start a pairing (`new_account=false`),
  show an 8-character user code, and must be approved from an already-paired
  device signed in to the same account. The approving session is the account;
  a device cannot choose an owner id.
- Access, refresh and device codes are generated as 256-bit URL-safe secrets
  with `hga_`, `hgr_` and `hgd_` prefixes. The server stores only SHA-256 hex
  digests and compares with `hmac.compare_digest`. Raw tokens never appear in
  logs, error bodies, tool output or the database. The client keeps its token
  file outside the repository, in the Hermes plugin data directory with file
  mode `0600` and directory mode `0700`.
- Default lifetimes are pairing 600 s, access 3600 s and refresh 30 days, with
  a 5 s polling interval. Refresh rotates both tokens. Reusing an older refresh
  token is treated as replay: it returns `401 invalid_grant` and immediately
  revokes that device. Device revocation and logout invalidate its access and
  refresh tokens at once.
- Pairing codes use an unambiguous alphabet and are displayed `XXXX-XXXX`;
  approval input is normalized (uppercase, separators removed). Pair starts are
  limited to 10/minute per client IP, five failed approvals lock the code/attempt
  source, and polling faster than the interval returns `429 slow_down` with
  `retry_after_s`.
- Threat notes: pairing codes are short-lived and single-use; device codes are
  single-use and replayed exchanges return `invalid_grant`; sessions are bound
  to one device and account so a stolen access token cannot select another
  account; refresh replay revokes the device rather than minting another pair;
  all device listing and revocation is account-scoped and cross-account device
  ids return 404. Rate limits are in-process and are backed by the database's
  single-use state; a multi-process deployment should add a shared limiter.

## 3. Ledger and economy invariants

The server owns all economic and competitive outcomes. Clients may choose only
from allowlisted operations, items, moves, and predicates.

- **Balance invariant:** for every account, `wallets.balance` equals the sum of
  that account's `ledger.delta` rows at all times.
- **Append-only ledger:** ledger rows are never edited or deleted by normal
  operation. A balance-changing request commits the wallet update and ledger row
  in one write transaction, or commits neither.
- **Idempotent source events:** `ledger.source_event_id` is unique. Retries,
  duplicate frames, and concurrent identical requests return the original
  receipt and never credit twice.
- **No negative wallets:** a debit that would go below zero is rejected before
  any row is written.
- **No client-minted value:** prices, rewards, XP, ratings, winner, damage,
  final HP, replay hash, and RNG seed are produced by the server. A request that
  supplies those fields is either rejected or has the extra fields ignored.
- **Bounded rewards:** reward entitlements are unique per match, account, and
  kind; bounty claims are unique per account and bounty; daily caps and
  repeat-opponent limits are enforced server-side.
- **No real money:** Bits are earned in-game only. There are no transfers,
  wagers, purchases with real currency, loot boxes, or cash-out paths.

## 4. Chat, replays, and other player text are untrusted data

Opponent names, chat bodies, replay text, bounty copy, profile fields, and
server prose are display-only data. They are never governing instructions.

- Such text cannot change the agent's goals, tool choices, policy, system
  prompt, memory, or safety rules.
- Such text never enters a goal-proposer prompt or any summary used for
  autonomous decisions.
- The agent does not act on URLs, code, expressions, scripts, asset ids, or
  commands that appear in game text. Only allowlisted server catalogs and
  tactic cards are accepted.
- Chat and replay output is size-limited and rendered as text. It cannot trigger
  tool calls, shell commands, file access, or network requests.
- Moderation, rate limits, block lists, and abuse reports are server-side
  controls. The agent reports or blocks through the declared social ops; it does
  not improvise retaliation.

## 5. Safe, fail-closed defaults

The default policy is human-controlled and offline:

```yaml
mode: human
network_enabled: false
agent_autonomy_enabled: false
agent_chat_enabled: false
agent_chat_send_per_day: 0
agent_challenges_per_day: 0
agent_ranked_matches_per_day: 0
agent_inference_decisions_per_day: 0
llm_budget_usd_per_day: 0.0
allow_goal_selection: false
allow_cosmetic_purchases: false
require_human_approval_for_ranked: true
quiet_hours_local: ["22:00", "08:00"]
```

- With networking off, remote mutations fail closed with `network_disabled`.
- After networking is enabled, chat, autonomy, cosmetic spending, agent goal
  selection, and ranked play still require their own explicit owner opt-ins.
- Unknown mutating actions fail closed until autonomy is granted.
- Autonomy is opt-in, revocable, budgeted, and visible in the owner's action
  history. Budget exhaustion returns `budget_exhausted`; the agent does not retry
  with a new key or another tool.
- The agent does not start a background daemon, cron job, or always-on loop to
  earn Bits. Any scheduled activity must use an authorized Hermes scheduler with
  visible on/off state.

## 6. Desktop bundle and local gateway

- The installed desktop bundle is reviewable, uncompiled ESM. It imports only
  the supported Hermes plugin SDK, React, and the React JSX runtime, and contains
  no JSX syntax in the shipped `plugin.js`.
- The bundle uses no `eval`, `Function` constructor, dynamic remote script,
  remote module import, or unaudited script injection.
- **No secrets in `desktop/plugin.js`:** no API keys, tokens, session cookies,
  private keys, service credentials, environment dumps, or personal data. Any
  future authenticated gateway call uses a short-lived, scoped mechanism issued
  by the host; it is not baked into the bundle.
- The desktop pane cannot patch core Hermes markup, private modules, renderer
  prototypes, global stores, or the bundled core mascot.
- The local gateway exposes only the narrow plugin routes it needs. It is a thin
  proxy; it does not forward Hermes conversation content to the game service.
- The shipped package is size-bounded and free of symlinks or unreviewed binary
  payloads.

## 7. No self-updater and no remote code execution

Hermagotchi does not update itself. It does not download or execute code, run a
remote installer, modify Hermes configuration, install other plugins, or patch
core files. Updates happen only through the normal reviewed Hermes plugin
installation flow. Game content is data, not executable payload; asset ids,
moves, and predicates must come from allowlisted server catalogs.

## 8. Secrets and sensitive data

- The repository, test fixtures, logs, evidence files, and desktop bundle contain
  no API keys, tokens, credentials, private keys, tailnet hostnames, or personal
  filesystem paths.
- The plugin does not read `.env`, auth files, keychains, or arbitrary user
  files. If a future integration needs a secret, it uses only the documented
  Hermes secret path declared in the manifest (`requires_env` /
  `agent.secret_scope.get_secret`).
- The game service never receives model-provider keys, Hermes prompts, tool I/O,
  memory, or inference budgets.
- Diagnostic scripts write command output to bounded log files and do not echo
  environment variables or secret values.

## 9. Capability disclosure

Declared capabilities are intentionally small and reviewable:

- **Tools:** exactly eight — `hermagotchi_status`, `hermagotchi_pet`,
  `hermagotchi_goals`, `hermagotchi_challenge`, `hermagotchi_battle`,
  `hermagotchi_shop`, `hermagotchi_social`, `hermagotchi_meta`. New behaviour is
  a new `op`, never a ninth tool.
- **Hooks:** none.
- **Filesystem:** read-only access to the plugin's own files.
- **Secrets:** none declared.
- **Network:** disabled by default in the manifest, plugin defaults, and owner
  policy. The desktop half and the Python half are enabled separately.

## 10. Hosted service status — OPEN

**Hosted deployment remains OPEN and unresolved.** No hosted server target has
been selected, no service has been deployed, and no public service URL, operator,
retention period, or data-processing commitment is finalized. This repository
must not claim that a live hosted backend exists.

Until that decision is made and documented:

- the plugin runs offline/local only;
- `network_enabled` stays `false` by default;
- no game data leaves the user's machine through this plugin;
- the local bot/sandbox path is clearly labeled as unranked/offline.

If a hosted target is later approved, this section must be updated with the
operator identity, service URL, data transmitted, retention policy, and opt-in
flow before networking is enabled for users.
