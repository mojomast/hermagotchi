# HERMAGOTCHI — Subagent-First Development Plan

**Version:** 0.1.0  
**Prepared:** 2026-11-05  
**Source of truth:** [`SPEC.md`](./SPEC.md)  
**Target:** Public plugin-catalog submission by **Wednesday 2026-11-11, 5:00 PM EST**, with a real <90-second demonstration.

> **Directive to the orchestrator:** You are responsible for delivering a working, installed and verifiable Hermes plugin, not a collection of independent prototypes. Use multiple bounded subagents in parallel where tasks are independent, integrate continuously, and keep a clear evidence trail. **Call an actual image-generation tool** to make the game's original creature and cosmetic assets. Their appearance must be modular, reproducible and demonstrably composed in the running product. Never substitute stock images, CSS-only placeholder blobs, raw image-generation prompts or unrelated completed character images for the real asset system.

## A. Execution contract (read first)

### Authority, deliverables and operating rules

1. Treat `SPEC.md` as the product contract. Keep a living `DEVPLAN.md` in the project repo; copy these files into the repo and update it after each gate.
2. Start by checking the target repository state, **current** Hermes version and official docs, configured image-gen providers, test tools and deploy target. Do not assume any repo, credentials, image-generation provider, or server environment is already available.
3. Perform a short **two-pass research loop**: (a) current upstream best practices/official Hermes SDK and catalog rules; (b) inspect current source tree and re-evaluate the guidance *in project context*. Record decisions and contradictions in `docs/RESEARCH.md`. Research is to de-risk implementation, not postpone it.
4. Do not modify Hermes core. Build a standalone, catalog-compliant unified package and a separable hosted service using public plugin surfaces. If an API is missing, feature-detect, degrade honestly or document a blocker; never monkey-patch renderer or private Hermes modules.
5. Work in independent git worktrees or nonoverlapping feature branches. Give each subagent **exclusive file ownership**. No simultaneous edits to a shared manifest or same file. Orchestrator owns cross-cutting contracts, integrations, releases and merge order.
6. Keep at most **3 implementation subagents concurrent** by default. Use a short-lived deblocker/research subagent when a slot is free. Do not oversubscribe models, image-generation quota, server environments or GPU resources.
7. Require structured handoffs: summary, changed files, commit SHA, test command/result, screenshots or contact sheets, known risks, API contract changes, next dependency. Integration is not complete until the orchestrator independently reruns evidence.
8. Prefer a thin vertical slice over broad scaffolding. **First prove an end-to-end match with purchase/equip in the Desktop pane and two separate identities.** Then polish, expand art and social details.
9. Every mutating operation is authenticated, idempotent, owner-authorized, and recorded where appropriate. Economic events are never trusted from agents/clients.
10. Stop or defer feature work when a release gate fails. No silent fallback from real multiplayer to mock matchmaking; no simulated credit presented as real balance; no unreported production auth shortcuts.
11. The hosted multiplayer service and asset generation may consume money/credentials. Obtain explicit user authorization for deploy/provider costs and do not put credentials in repository or tool output. Use no external network until configured/consented.
12. Produce the demo and catalog PR while time remains. Leave a submission buffer; don't ship an untested refactor at the deadline.

### Required final repo outputs

- Working `plugin.yaml`, `__init__.py`, schemas/tools and agent skill, `dashboard/plugin_api.py`, `desktop/plugin.js` native pane and a documented install/enable path.
- Hosted multiplayer game service plus local reproducible development server, schema migrations, deterministic combat engine, balance/ledger, item catalog/inventory, leaderboard, bounties and chat.
- Original image-generated creature and cosmetic art, modular composition rig, machine-readable asset manifest, generated packaging, prompt/provenance records, QA contact sheets and a verified sample of at least 100 combinations.
- Automated tests for game integrity, economy concurrency, authorization, agent policies, endpoint contracts, plugin loading and visual asset validation.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/RESEARCH.md`, `docs/DEMO.md`, screenshots, a short demo capture, submission instructions, and an honest `HANDOFF.md`.
- A Git commit to pin, an open catalog PR if access is available, and a ready-to-post demo + links (posting under user's identity requires user authorization). Record remaining manual submission steps clearly.

## B. Known upstream constraints to verify before coding

**Verified as of 2026-11-05 (links in SPEC.md):**

- Python plugins have `register(ctx)`, tools, hooks and manifest declarations. `hermes plugins doctor` and `hermes plugins validate <dir> --install-deps` are official checks.
- Desktop ESM plugins can register pane/status-bar contributions; `desktop/plugin.js` is uncompiled, uses `jsx()` / `jsxs()`, and only imports the approved SDK/React specifiers.
- A unified package may include `plugin.yaml`, agent files, `dashboard/manifest.json` + `plugin_api.py`, and `desktop/plugin.js` in one repo.
- Desktop code calls the plugin's local gateway API with `ctx.rest`; `ctx.socket` is not guaranteed on every remote. Use `host.onEvent` and polling for eventual consistency.
- Native desktop package copy is constrained (<64MB, no symlinks); the backend has a **separate** enable gate.
- Catalog enforces declared capabilities, no self-updating code, no core overrides, safe credential paths, a reviewed 40-character SHA, disclosure of external services and no unscannable executables.
- Hermes supports `image_generate` through configured image-generation providers, including image-edit/reference capabilities on supported backends. The agent must confirm a working provider and rights/budget before generating.

**Do not assume:** direct binary image URL loading in the renderer, permanent access to any model, a particular OAuth sign-in workflow for Hermagotchi, an existing configured game server, or the current Hermes build's exact required minimum version. Spike/validate each.

## C. Work decomposition and ownership

Use three implementation tracks in waves; orchestrator coordinates integration. In each wave, assignments are bounded, with explicit contracts and gates.

| Track | Owner | Exclusive ownership | Responsibility |
|---|---|---|---|
| **A — Server & Rules** | Subagent A | `server/**`, `server/tests/**` | API, identity verification, DB/migrations, combat, Bits/ledger, bounties, rating, chat, abuse limits |
| **B — Art & Rendering** | Subagent B | `art/**`, `assets/**`, `scripts/asset_*`, `scripts/render_contact_sheet.py`, `desktop/src/renderer/**` | Image generation, alpha cleanup, rig/anchors, combinatorial variations, deterministic layered renderer, QA sheets |
| **C — Hermes & UI** | Subagent C | `__init__.py`, `plugin.yaml`, `schemas.py`, `tools.py`, `skills/**`, `game_client/**`, `dashboard/**`, `desktop/src/ui/**` | Plugin tools, policies, Desktop SDK, pane screens, local backend, cloud API bridge, owner UX |
| **Integrator** | Orchestrator | `shared/**`, `tests/**`, root files, `desktop/plugin.js`, CI, releases, deployment docs | Schema freeze, merge order, packaging, true E2E, CI, catalog validation, risk management |

**Integration boundary:** Track B exposes an asset/rendering function from developer-source modules, consumed by C *before build*. Integrator builds the final single `desktop/plugin.js` as reviewable uncompiled ESM. If the packaging constraints prevent separate imports, bundle at build time without dynamic imports/eval/remote scripts. Track A generates only server contracts based on shared schemas owned by integrator. If a track needs to edit someone else's file, request a contract change, not an overlapping write.

### Subagent handoff template (every task)

```markdown
## Task ID / branch / commit
**Scope completed:**
**Files changed:**
**Contract consumed/produced (exact schema version):**
**Tests run (commands, counts and outcome):**
**Visual evidence / screenshots / artifact paths:**
**Security and privacy implications:**
**Unresolved failures or assumptions:**
**Integration notes / requested changes:**
**Next recommended action:**
```

**Do not accept:** "works", "tests pass" without commands and outputs, missing generated assets, unspecified test scope, or a claim that an agent called an API without network evidence.

## D. Schedule and hard gates

The target is short. The dates below are **suggested time boxes**, not a claim that any work has already happened. Adapt pace to real progress, but protect submission time. Prefer frequent merges of small proven changes over a long branch merge at the end.

| Window | Gate | Proof required | Abort/trim trigger |
|---|---|---|---|
| Nov 5 | **G0 Research & feasibility** | Hermes release + SDK verified; image-generation provider confirmed; real deployment/auth path decided | If image gen or remote server unavailable, escalate immediately rather than fake demos |
| Nov 6 | **G1 Contracts + thin install** | Plugin doctor, Desktop pane appears, health/read-only status via gateway; schema fixtures frozen | No free-form feature expansion before installer works |
| Nov 7 | **G2 True game vertical slice** | Two identities adopt, challenge, deterministic match, Bits awarded exactly once; server tests | Cut optional chat features if battle/reward not real |
| Nov 8 | **G3 Modular visuals and shop** | 3 generated species + compatible layers, 12 cosmetics, 100-loadout QA, purchase/equip propagated | If image layers are poor, prioritize aligned 3 species/6 hero items, transparently record shortfall; no fake compliance |
| Nov 9 | **G4 Hermes agent + social** | Agent can choose goal/tactics within budget; leaderboard, bounties, chat safely integrated; 2-install E2E | Freeze feature scope after gate |
| Nov 10 | **G5 Release candidate** | CI green, catalog validator green, privacy/security tests and screenshots, public deploy verified, 90s demo captured | No risky refactors; bug fixes only |
| Nov 11, before 5 PM EST | **G6 Submit** | Public repo pinned SHA, catalog PR, video on X tagging Nous, submission form completed/ready with links | Stop coding early enough to handle review/submit friction |

**Daily rule:** maintain `docs/STATUS.md` containing tasks, owners, blockers, green/red gates and next integration. Each day ends with the best demonstrable runnable build, not an unmerged speculative branch.

## E. Phase 0 — dual-pass reconnaissance (orchestrator, max ~half day)

**Actions:**

1. Identify current local checkout, installed Hermes executable/version, required Node/Python versions, plugin testing commands, Docker/PG availability, image-generation provider, hosting target and API credentials *without printing secret values*.
2. Read official Hermes docs linked in `SPEC.md` and representative example plugins; inspect `apps/desktop/src/sdk/index.ts` only if needed to confirm exports and feature detection. Read complete catalog admission rules, especially Desktop surface and credential restrictions.
3. Search for pre-existing virtual pet, renderer, or combat code in the **working repo only** and compare reuse vs direct new implementation. Do not fork bundled Petdex or violate bundled-skin catalog rule. Analyze licensing before reuse of any art/code.
4. Research practical modular 2D sprite production: shared canvas/rig anchors, transparent alpha, non-destructive segmentation, metadata-driven z-order, visual regression, render batching and reduced-motion. Record sources/decisions.
5. **Re-research in context**: after inspecting repo/build pipeline, validate whether a transpiled build to `desktop/plugin.js` is permitted, whether data URIs render, and whether gateway routes are accessible from native Desktop. Check a real installed Hermes build, not just docs.
6. Identify server state/identity approach that uses allowed Hermes secret handling. Define network opt-in UX and target service privacy disclosure.
7. Create `docs/RESEARCH.md`: date, checked URLs + applicable version, candidate approaches, chosen approach, conflicts, unresolved issue, test used to settle it, accepted design record.

**G0 evidence:** minimum three small spikes:

- `S0-DESKTOP`: plugin enables and contributes a pane, no unsupported imports.
- `S0-ASSET`: one 512x512 generated transparent creature body plus one headwear layer composited at multiple sizes, with alpha/pixel checks. This is *real* image generation, not placeholder art.
- `S0-NETWORK`: installed plugin can read private authenticated read-only `/me` through approved gateway route without exposing credentials to Desktop.

**Gate failure:** if a spike fails, orchestrator assigns a deblocker with a 1-2h bounded investigation and records an explicit decision. Do not start complex backend UI work assuming the failing interface exists.

## F. Phase 1 — contract freeze and skeleton (G1)

### Orchestrator tasks

- Write `shared/schema/` JSON schemas for `PetPublic`, `PetPrivate`, `Appearance`, `Item`, `Wallet`, `LedgerEntry`, `Challenge`, `TacticCard`, `Match`, `ReplayEvent`, `ChatMessage`, `Goal`, `Policy`, `ApiError`, `GameEvent`.
- Define names, version keys, numeric units, enum IDs and example fixture JSON; issue `contracts-v1` tag/commit and circulate to all tracks.
- Freeze the z-order/slot vocabulary early: `head`, `face`, `back`, `front`, `aura`, `emote`, `habitat`, `title`. All subagents use identical IDs.
- Define idempotency key header, server error envelope, auth proof, timestamps, pagination cursors, content sizes, update sequence and offline behavior.
- Run a repo-level skeleton end-to-end: `desktop/plugin.js` loads, `ctx.rest('/health')` calls `plugin_api.py`, returns gateway health; agent's `hermagotchi_status` reads same local client. Document separate enable toggles.

### Track A tasks

- Create `server/` executable app, versioned migrations, minimal accounts/pets/health routes, deterministic fixtures and local test database.
- Add request-validation and error-code handling; no wallet writes without unique source event.

### Track B tasks

- Author `art/STYLE_GUIDE.md` (view, outline weight, palette, pose, silhouette and contrast).
- Generate initial style board and 3 approved master creature designs with `image_generate`, using matching references; record every tool use in provenance.
- Implement manifest loader/schema and composite renderer proof-of-concept (one body, hat and face layers).
- Prototype deterministic seed-driven trait rendering. Emit 12 thumbnail sheet before expanding.

### Track C tasks

- Implement loadable plugin manifest/tool stub and a native pane/status chip using Hermes SDK only.
- Build opt-in settings and clear `backend disabled`, `network off`, `auth missing`, `service unavailable` states.
- Implement local client adapter and one read-only live status flow through gateway.
- Avoid direct third-party `fetch` from the renderer for user tokens.

**G1:** Test Hermes cold start, enable/disable, install from file and linked dev package, plugin doctor, coherent local/offline screen, no network until opt-in, and one successful backend read.

## G. Phase 2 — server economy and battle (G2)

### Track A: exact sequence

1. Database migrations and constraints: `accounts`, `pets`, `wallets`, `ledger`, `matches`, `tactics`, `rewards`, `ratings`, `inventory`, `equipment`, `challenges`.
2. Authentication: account and approved device/pairing scheme (see G0); user-scope ownership checks, revocation, token handling and request ID logging. No unsecured/demo fallback in production mode.
3. Pet adoption: 3 species, stable seed, uniqueness per account, pet revision/CAS, server-time care updates with bounded decay.
4. Implement pure `resolve_match(ruleset, pet_a, pet_b, tactics_a, tactics_b, seed) -> Replay` with deterministic status/move/cooldown semantics and round cap. Commit golden fixtures and replay SHA.
5. Challenges: create -> invited -> accepted -> tactics submitted -> resolved/expired. Enforce single resolution path with transactions/locking.
6. Award ledger entitlement and rating in same transaction when valid; retries see already-resolved match and return same receipts. Cap duplicates, repeated account pairings, practice rewards and daily earn.
7. `POST /shop/purchases`: transactions/constraints ensure exactly once; `equip` checks inventory and compatibility.
8. Rank and bounty queries; implement at least 3 server-evaluable bounties.

### Track C: integration sequence

- Use G1 client to adopt, show status, invite/accept, submit tactic card and play replay. Provide manual buttons in Desktop before adding agent autonomy.
- Add `hermagotchi_challenge` and `hermagotchi_battle` tools with enumerated actions, typed payloads and deterministic errors.
- Display wallet receipt with source entitlement ID and match ruleset/rating change.
- Ensure same server result rendered after reconnect/restart.

### Contract and test examples

```
TEST: two accounts A/B adopt; A invites B; B accepts;
      A submits aggressive, B defensive; server resolves once.
EXPECT: replay identical on A and B, each sees same winner,
        wallet balance equals ledger, one rating update each (ranked only).
RETRY: resubmit same tactic/resolve/reward 100 times concurrently.
EXPECT: exactly one match, one entitlement per eligible participant,
        no duplicate ledger row, consistent replay hash.
```

**G2:** Run server integration with *two separate auth identities*, not a single mocked client. Do one live network run across two distinct local sessions or machines. Screenshot the two states and record correlation/match ID. If server cannot be deployed publicly yet, record local real HTTP success and promote to hosted G4.

## H. Phase 3 — generation-driven modular art (G3; run in parallel from G0)

**This track must actually use image generation, not merely plan to use it.** Track B is accountable for visual quality. Orchestrator independently reviews actual PNGs and contact sheets.

### H1. Generate real source art

- Use a configured **reference/edit-capable** image-generation tool (`image_generate` on a verified Hermes backend, or another explicitly available provider). Do a small cost/availability probe; get approval before paid batches. Keep provider details, prompts, reference inputs, outputs, hashes and rights notes in `art/PROVENANCE.md`.
- Generate cohesive style board, three *different silhouettes*: Byteblob round, Patchfox ears/tail, Nullgeist floating/gaseous. Approve against `art/STYLE_GUIDE.md` at 96px before producing accessories.
- Make at least 2 eye styles, 2 marking styles, 2 palettes per species. Where editing produces a full creature, **extract only the changed layer**. Transparency must be verified, not inferred from visual checkerboard.
- Generate 12+ shop cosmetics including a prestige crown, wizard hat, visor, face mask, cape/wings, aura set, emote, habitat item. Keep a unique style; no third-party brand logos or recognizably copied characters.
- Preserve approved identity with reference images rather than regenerate inconsistent variants from scratch. Reject equipment that cannot fit the common rig; create per-species anchor/asset overrides where needed.

### H2. Build the modular compositing machinery

- Define shared 512x512 canvas, neutral pose, baseline, species anchors and masks; each layer must share that canvas and transparent RGBA dimensions.
- Create rig `small_front_v1`, slot bounds, offsets, scale/pivot, z-order, occlusion, compatibility and face transforms in `assets/manifest.json`. Give species feature layers independent IDs.
- Implement `render_pet(snapshot, pose)` as a pure deterministic chooser/renderer; assets are data, pet appearance seed never re-rolls on refresh. Confirm same hash for same input on two renderers/installs.
- Animations should move attachment anchors with body/head transforms. Define fixed states `idle`, `blink`, `happy`, `attack`, `hurt`, `win`, `lose`. Prefer a tiny transform grammar (bob/jump/squash/rotation) over per-item sprite animations.
- Pack images for Hermes native ESM by tested data URI embedding or a proven authenticated backend route. Generated build output must use only allowed imports; source tree may use build tooling but runtime cannot inject remote scripts.
- Optimize alpha/bytes; ensure desktop package <64MB and fast initial render.

### H3. Visual QA gates

- `asset_validate.py`: checks RGBA dimensions, non-empty alpha, sensible alpha bounds, hash, pack size, manifest path, duplicate IDs, valid anchors/z-order, compatible slots, no off-canvas overflow.
- `render_contact_sheet.py`: at least 100 seeded creatures, thumbnails at 96/160/256px, all equipment per compatible species, colorblind-readability spot-check, dark and light backdrop checks, expression/animation sample states.
- Visual reviewer opens sheets; reports floating hats, horns clipping, wrong z-order, fake transparent backgrounds, leftover reference-character pixels, jagged alpha halos, inconsistent line weights, missing items. Repair/regenerate, rerender.
- Add screenshot/golden tests for 20 canonical seeds and a compositing contract test that every owned/equipped cosmetic actually renders.

**G3:** real PNGs + editable source/provenance + 3 distinct bases + 12 visible products + 100 tested combinations, with verified bundle, not just a slick single screenshot. If fewer items are completed, report exact shortfall; don't re-label incomplete art as complete.

## I. Phase 4 — native Hermes UX and agent behavior (G4)

### Track C: UI functionality

- One native pane with tabs: `Habitat`, `Battle`, `Shop`, `Leaderboard`, `Chat`, `Settings`. Use `ctx.register({area:'panes',...})` and plugin SDK UI primitives; avoid JSX syntax in final disk module.
- Habitat: pet art, care meters, XP, mood/emotes, agent goal progress, mode indicator, next unlocked cosmetic.
- Battle: challenge list/accept, opponent avatar/loadout, tactic choices, turn-by-turn replay and victory/defeat animation. Prefer workspace expansion only if SDK `host.openWorkspace` is feature-detected; pane fallback required.
- Shop: Bits and price, ownership badges, compatible slots, preview and purchase/equip UX, no spend until verified server response.
- Leaderboard: top 50 and personal neighborhood, season/rank label; clicking competitor opens sanitized profile/appearance and explicit challenge action.
- Chat: lobby and challenge thread, human-vs-agent visible labels, mute/block/report, structured permission toggle and unsent drafts by default.
- Settings: multiplayer URL/opt-in, identity, chat, autonomy, max challenges, inference budget, quiet hours, disconnect/delete, diagnostics and software versions.
- Reconnect correctly from REST snapshots; use gateway events to invalidate queries and poll fallback if no usable socket; no tight polling loops.
- Dark/light theme, 240px pane, reduced motion, keyboard, mute and transparent alpha previews verified.

### Track C: agent tools and objectives

- Register typed tools listed in SPEC; docs/skill describe exact modes, safe actions and reasons to battle, collect Bits, spend on cosmetics and climb rank.
- Agent planning input is an **allowlisted summary**: goal, price, balance, battle readiness, permitted opponents, eligible bounties and budget. No chat content in a system prompt. Resist injection from opponent names/taunts/messages.
- Implement a zero-token tactic/goal heuristic and an optional LLM-assisted mode gated by explicit owner consent/inference budget. Keep total output schemas short. An LLM should not invoke `image_generate` to play a battle.
- Logs show every agent decision, tool action and user setting that allowed it. A user can switch to Human mode or cancel future auto-play immediately; existing authenticated server results still reconcile.
- Agent can buy/equip cosmetics only when the owner sets `allow_cosmetic_purchases`; Bits are virtual, but spending owner-earned progress still needs explicit permission.
- Battle invitations received from other agents require owner permission to auto-accept, separate from permission to issue challenges.

### Track A: social and leaderboard

- Authoritative leaderboard query with deterministic ties and ranking version.
- Server-filtered lobby and match-thread chat with size bounds, allowlist, moderation flags, blocks, report and pagination; all text treated untrusted on clients.
- Battle notifications and optional lobby event stream; every event has monotonic sequence, stable ID, resync endpoint.
- Cap agent outbound messages; agent-labeled message is provenance, not privileged instruction. No stored chat prompts fed into autonomous tools.

**G4:** Two real account instances chat, challenge, spectate the same replay, see leaderboard rank and cosmetic appearance. With agent mode enabled by owner, one Hermes makes a bounded meaningful gameplay choice visible in its tool trace. With autonomy disabled, no network/battle/chat action originates from an agent.

## J. Phase 5 — hardening, deployment and catalog submission (G5/G6)

### J1. Test matrix (run, do not infer)

**Unit / property**

- Pure game replay same seed/inputs -> identical canonical event digest on 100+ cases; round limit and no negative HP; invalid move rejected; status/cooldown precedence tested.
- Wallet invariant `balance == sum(ledger.delta)` across mixed rewards/spends and 100+ concurrent identical requests.
- Duplicate purchase, replayed entitlement, reordered webhook/event, expired challenge, disconnected account, double tact submission.
- Bounty claims one-time; illegible/no-op agent activity cannot mint Bits; anti-farm limiter tested.
- Seeded renderer paths stable; rig anchors within bounds; missing/unowned cosmetic cannot appear when server state is invalid.

**Security**

- User B cannot mutate A's pet/inventory/wallet or read A's private data.
- Modified client payload cannot award Bits, pick outcome, change rank, force match or use an unowned item.
- Chat prompt-injection strings are safely escaped, size-limited and do not enter agent tool policy contexts.
- Network and autonomy default off; zero private prompts, secrets, memory, tool inputs/outputs sent off-host even with voluntary play enabled.
- Device revocation blocks further calls, tokens never appear in `desktop/plugin.js`, URL query params, screenshots or public logs.
- Invalid API endpoint / upstream downtime -> bounded retry, no wallet double-spend, readable error.
- Security scan + declared capabilities + dependency pins + no unscannable binaries + no self-updater verified.

**Hermes integration**

- Cold start, enable/disable both halves separately, profile switch, remote backend limitation, plugin restart, stale copy detection, hot reload and disposal.
- If `ctx.socket` absent, polls reconnect and catch up. If backend disabled, pane shows setup status.
- No unsupported imports/JSX/dynamic imports, global DOM injections or private Hermes core overrides.
- Install docs work from a fresh machine/profile, including separate Python enable path.

**Visual and experience**

- Contact sheets reviewed, real generated art with provenance; 3 species, >=12 cosmetics; 100 seeded outfits.
- No layering defects at 96px/256px; same battle replay on both screens; cosmetic purchase visibly changes pet.
- Native theme compatibility, keyboard/screenreader labels, reduced-motion and mute.

### J2. Deployment

- Containerize server from reviewable source with reproducible dev config, migrations and example environment variable names but no secrets. Production PostgreSQL with TLS; one instance sufficient for hackathon, optional Redis only if proven necessary.
- `docker compose up` or equivalent local path with deterministic seed fixtures; test remote URL separately before publishing.
- Production defaults: structured logging redacting auth, rate limiting, maximum request size, CORS/auth scopes, healthz, restart policy, DB backups, admin ability to ban/report/reconcile, cost controls and dashboard/alerts.
- Do not open player-machine inbound ports. Desktop and Python plugin use HTTPS outbound to hosted service. Domain/URL must be user configurable, documented, and exposed in network consent.
- Use staging credentials and service tests before a real public demo account; label fake sample data when shown. Plan for service outage and include a local reproducible two-account demo, but **never depict offline bot as real PvP**.

### J3. Plugin catalog gate

1. Check the *current* catalog requirements and official hackathon post again. Confirm `requires_hermes` is a real compatible SemVer floor; synchronize plugin manifest and catalog entry.
2. Pin dependencies with realistic upper bounds; no self-updating plugin code, no opaque binaries/wasm, no runtime core patching, no reading credentials from files.
3. Add `README.md` disclosure: hosted service operator, remote endpoints/network calls, user metadata, chat behavior/retention, optional schedules, account setup, costs, permission/secret storage, limitations, removal/data-deletion process.
4. Run `hermes plugins doctor <plugin-path>` then `hermes plugins validate <plugin-path> --install-deps`; capture logs. Resolve warnings that would block manual review.
5. Create catalog YAML in `NousResearch/hermes-agent` PR with **full 40-character SHA**, matching version, accurately declared tools/hooks/requirements, screenshots. Do not state catalog acceptance before maintainer review/merge.
6. Record Git PR URL (or a ready-to-apply diff if no repo permissions). Capture 60-90s no-fake demo and publish only when user authorized; tag `@NousResearch`; submit both links through official form per announcement.
7. Freeze/fix release candidate; produce a reproducible handoff with exact commit, service endpoint, setup/test commands, known gaps, and all mandatory links.

## K. 90-second demo storyboard

A polished *single continuous story* scores better than disconnected screenshots. Show actual network identity/battle IDs if necessary without revealing secrets.

| Clock | Action | Visual proof |
|---|---|---|
| 00:00-00:10 | Start Hermes Desktop plugin, show agent-owned Patchfox and separately human-owned Nullgeist | Native pane and distinct composited art |
| 00:10-00:21 | Open agent goal: "Save for Binary Crown" and active bounty | Goal progress, Bits and settings |
| 00:21-00:32 | Hermes chooses valid tactic card and sends a challenge; other instance accepts | Two accounts/agent tool evidence; not mock |
| 00:32-00:52 | Play real deterministic 1v1 replay with animated modular sprites | Distinct tactics, move effects, outcome from hosted server |
| 00:52-01:01 | Wallet/XP/rank awarded, leaderboard updates | Ledger receipt and rank movement |
| 01:01-01:13 | Agent buys/equips new cosmetic and it appears on both screens | Modularity, persistent inventory and synced look |
| 01:13-01:22 | Agent sends one permitted playful chat line; other user reacts | Labeled safe social chat |
| 01:22-01:29 | End on 3+ differently dressed creatures and install path | Hook, creativity, clear call to install |

If no ranked match within time, use a pre-arranged consented second account with a pending real challenge. Pre-capture footage is acceptable if events are real and no result is fabricated. Edit down slow wait states, **never** fake API responses or values.

## L. Prioritization, pruning and failure management

### Must not cut

- Real Hermes plugin integration and native Desktop pane.
- One real hosted two-owner PvP encounter, deterministic replay and once-only Bits reward.
- Actual original image-gen assets, modular layers and a working equipped cosmetic.
- Basic leaderboard, safe chat/permissions and agent-generated valid decision.
- Security/catalog-compliance checks, real submission artifacts.

### Cut in this order when late

1. Complex battle animations and sound; retain clear idle/attack/win states.
2. Social flair: guilds, rivals, voice, chat rooms beyond lobby/match thread.
3. Cosmetic category breadth beyond minimum; retain at least one visible option per major slot and a compelling crown goal.
4. Extra bounties, seasonal ceremony, advanced rating beyond Elo.
5. Cron-driven autonomous scheduling; retain human-invoked agent gameplay with explicit goals and permissions.
6. Optional browser web dashboard and remote spectator page.

If production auth or cloud deploy is blocked, **flag as a critical G4 blocker**, never auto-fallback to pretending multiplayer works. If image generation is blocked, **flag as a critical G3 blocker**; report available providers and required owner input instead of faking art. Continuing other independent work is fine.

### Stop-work triggers

- Unauthorized transactions or cross-account data leak.
- Duplicate currency grants/purchases under retries or races.
- Unverified cloud identity or exposed secrets.
- A proposed plugin technique violates catalog rules or bypasses host approvals.
- Image assets cannot align and would make cosmetic purchases visually misleading.

## M. Definition of done and evidence ledger

Before marking shipped, the orchestrator must fill out this table in `HANDOFF.md`:

| Area | Exact evidence to supply |
|---|---|
| Source | repo URL, release tag and full commit SHA |
| Hermes | tested version, plugin doctor + validate logs, cold-start screenshot |
| Multiplayer | two separate identity IDs (redacted), challenge/match IDs, authoritative replay hash |
| Economy | transaction/ledger reconciliation output, concurrency test outputs, purchase/equip receipt |
| Assets | image-gen provenance, original source PNGs, rig manifest, 100-seed contact sheets, bundle size |
| Agent autonomy | policy snapshot, goal-selection tool trace, quota enforcement and off-switch proof |
| Social | chat opt-in, block/report, injection test output |
| Operations | deployed URL, auth flow, backup/restore notes, outage behavior, cost notes |
| Delivery | README, install path, demo clip, catalog PR, required social post/form status |
| Gaps | incomplete features, known defects, next 3 prioritized issues |

A feature only counts when it has real code + passing tests + manual integration evidence, not an agent's self-report. Note what was *not* tested.

## N. Initial task tickets to dispatch

These are written so the orchestrator can copy/paste to subagents and start three tracks in parallel **after issuing contract stubs**.

### A-01 — Authoritative backend core

> Implement the Hermagotchi hosted API, database migrations, deterministic match engine and once-only Bits ledger using `SPEC.md` and frozen shared schemas. You own `server/**`. Read current relevant best practices and Hermes-independent backend security guidance, then inspect the repository and re-evaluate these choices. Start with a two-account E2E test, then add rated matches, bounties, item purchases and proper transactional semantics. Use typed contracts, idempotency keys and no client-calculated outcomes. Deliver commits, passing tests, replay fixture/hash, race-test output, endpoint map, deployment instructions and unresolved assumptions. Never invent auth credentials or relax authorization in production.

**A-01 acceptance:** two real authenticated accounts complete one match; server ledger and rating reconcile after 100 duplicate/concurrent requests; tests and migrations reproducible.

### B-01 — Original generated creature art and modular renderer

> You own `art/**`, `assets/**`, asset scripts and `desktop/src/renderer/**`. **You MUST actually invoke a configured image-generation tool** for original species and cosmetics. Confirm provider, price/budget and edit/reference capability; create a consistent style board and 3 distinct species; extract transparent body, expression, feature and equipment layers to a canonical 512x512 rig. Build manifest (anchors, z-order, occlusion, compatibility), deterministic seed-based feature/palette selection, animated layered renderer, 12 shop cosmetics, original/source/provenance records, 100 seeded contact-sheet QA and validation scripts. Where editing generates a complete pet, isolate individual layers with masks instead of pretending the entire output is a modular accessory. Re-research alignment/asset packaging in the context of this repo and actual Hermes SDK restrictions. Do not use copyrighted sprites or logos. Handoff with real generated files, screenshots, tool generation count/cost, build size, tests and unfixed visual problems.

**B-01 acceptance:** visually reviewed sheet with >=100 loadouts, transparent RGBA all layers, three clearly different silhouettes, 12 unlocks, stable visual hashing and a demonstrable actual buy/equip change in integrated preview.

### C-01 — Unified Hermes plugin and native UI

> You own Python plugin files, game client, dashboard router and `desktop/src/ui/**`. Implement one compliant Hermes package: tool registration, policies, approved secret handling, opt-in network, native pane and status chip, read-only health/status and initial adopt/challenge/purchase UI. Use SDK-only imports, uncompiled `jsx()` in the generated release, `ctx.rest` gateway backend, proper separate enable gates, and event/poll fallback. Investigate the live Hermes version and relevant official docs before coding; re-evaluate against the actual repo and Desktop install. The first milestone is `hermes plugins doctor` and a working pane through an authenticated backend. Next connect the signed shared API schemas and real gameplay. Do not read `.env`/auth files or patch core. Deliver exact install/test commands, screenshots, user opt-in flow and security notes.

**C-01 acceptance:** loaded package on real Hermes, separate on/off controls, read-only backend flow, tool call, no unauthorized outgoing traffic, real shop/equip and remote match state presented after integration.

### I-01 — Integration / deblocker (orchestrator)

> Own cross-track contracts, enforce versioned schema fixtures, build allowed single-file Desktop ESM and run real two-identity end-to-end tests. On a blocker, assign a timeboxed independent deblocker task to the next available subagent slot, demanding a reproducible probe and recommendation. After each integration gate, update `DEVPLAN.md`, `docs/STATUS.md`, `HANDOFF.md` and run regression tests. Protect hackathon submission work. Do not accept handoffs solely on self-reported successes.

## O. Continuous improvement after the hackathon (separate backlog)

- More rigs and species; user-submitted moderated cosmetic designs; custom habitat layout and animation editor.
- Guilds, bracket tournaments, cooperative raids, authored replay sharing, seasonal collectibles and cosmetic awards.
- Breeding/evolution paths and non-tradeable inherited look traits with bounded combinatorial state.
- Full 2D skeletal renderer if scale requires it, shared public spectator web UI, opt-in guild chat; only after privacy/moderation plan.
- Federated servers, offline signed battle tactics, hosted-service portability, more robust anti-collusion and player support tools.

---

### Source-of-truth reminder

The spec defines **what must be true**. This plan defines **what to build and verify**. Any contract change requires a documented rationale, change to fixtures/schema, affected subagents notified, and proof it preserves the integrated product. Keep shipping evidence ahead of feature claims.
