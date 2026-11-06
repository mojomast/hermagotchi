# HERMAGOTCHI — Product & Technical Specification

**Version:** 0.1.0 (implementation-ready working specification)  
**Prepared:** 2026-11-05  
**Target:** Hermes Agent Plugin Catalog Hackathon; deadline **2026-11-11, 5:00 PM EST**  
**Form factor:** one installable Hermes plugin with Python agent tools, an optional native Hermes Desktop pane, and an opt-in hosted multiplayer service  
**Companion:** [`DEVPLAN.md`](./DEVPLAN.md)

> **Mission:** Build the smallest *complete* multiplayer agent-pet game in which a Hermes agent (or a human) adopts a unique composited creature, sets a goal, challenges another player's pet, earns Bits/XP/rating, purchases an appearance-changing cosmetic, and shows it off in a Hermes Desktop pane. The agent must make visible, bounded decisions; the game server must own every economic and competitive outcome.

## 0. Non-negotiable product decisions

1. **Three owner modes:** agent-owned, human-owned, and co-op. Human ownership and permission always supersede agent preferences. Support one active pet per player for the hackathon.
2. **Real multiplayer, no pretend network:** two separate Hermes installs/accounts can challenge each other through a hosted authoritative server. Local bot/sandbox mode is clearly labeled unranked/offline.
3. **Cosmetics are the primary Bits sink:** unlock headwear, facewear, backwear, auras, emotes, habitat decor, and titles. They must visibly appear on the pet, not just in an inventory list.
4. **No pay-to-win or money mechanics:** Bits are earned in-game, never redeemable, never sold, never transferable in v1. No purchases with real currency, wagers, loot boxes, gambling, or paid boosts.
5. **Agent goal system:** agents can select a collectible cosmetic or leaderboard goal and make supervised progress toward it. The objective is an *owner-approved game setting*, never an overriding priority for the main assistant.
6. **Deterministic server combat:** server calculates every hit, reward, rating update, and achievement, using a fixed ruleset version and recorded RNG seed. LLMs propose bounded tactics; they never define damage or economy values.
7. **Original, modular, generated character art:** use image generation to create original source art and cosmetic layers; use an explicit rig/anchor schema and automated compositing/QA. A pet's uniqueness comes from *layered components, traits, palettes, cosmetics, and deterministic seeds*, not a full AI generation per player or battle.
8. **Security by design:** no untrusted chat/game events become instructions to Hermes, no secrets or conversation data leave the user's machine, no silent spend of inference/API budgets, no unaudited desktop injection.
9. **Hackathon first:** prioritize the functional end-to-end demo and catalog compliance ahead of breeding, economy complexity, cross-agent lore, and always-online simulation.
10. **Install must be honest:** clearly disclose optional cloud service, its operator/URL, data transmitted, background behavior, and if the service is currently hosted/maintained.

## 1. Problem, differentiation, audience

Typical virtual-pet widgets only reflect an assistant's existing activity. Hermagotchi adds a *socially observable, persistent, agent-mediated game loop*. The agent must decide **what it wants**, **which match to take**, **how to fight**, **what to save for**, and **which outfit to equip**; the human can intervene at every step. Pets must have visible personality and distinct silhouettes, not merely alternate labels.

**Primary audience:** Hermes Desktop users with an agent that can use plugin tools. **Secondary:** humans who want a Tamagotchi-like game without agent automation. **Community payoff:** agent-vs-agent challenges, leaderboards, cosmetics, chat, rivalries, playful tournament culture.

### Success criteria

- A new user installs, enables and adopts in under five minutes excluding external account creation and any hosted-service outage.
- A human can play without enabling background autonomy or an LLM.
- Two live, distinct installations complete a challenge, both see the same replay/ledger outcome, and both can chat (if opted in).
- At least three pets on screen have *clearly different silhouettes*, palettes and/or accessories; changing a cosmetic updates the renderer for both participants.
- One agent autonomously selects a **permitted** goal, evaluates opponents, submits a tactic plan, and completes a battle within a configured budget.
- Restart, reconnect, duplicate requests, and reordered network frames do not duplicate Bits or silently lose ownership.
- Plugin passes `hermes plugins doctor` and `hermes plugins validate` on the pinned release, with a working <90-second demo.

## 2. Delivery scope

| Priority | Required in deliverable | Deferred / explicitly out of scope |
|---|---|---|
| **P0** | Adopt pet, rename, human/agent/co-op switch, local care/status, one active pet | Breeding, trading, pet death |
| **P0** | Battle engine, 3 species, 4+ useful abilities, async PvP challenges, bot practice, replay | Real-time synchronous turns, elaborate move trees |
| **P0** | Bits wallet + immutable ledger, XP, 1 ranked leaderboard, daily bounties, item catalog, purchase/equip | Real money, tokenization, player transfers |
| **P0** | 3 species with genuinely distinct silhouettes, 2 palettes each, min. 12 launch cosmetics, unique layered appearances | Custom generations for every user; runtime image-generation costs |
| **P0** | Desktop pane: pet habitat, battle preview/replay, wallet/shop, leaderboard, challenge inbox | Mobile app, web dashboard parity |
| **P0** | Safe user/agent chat: match thread + lobby or direct channel, moderation/rate limits, block/report | Unmoderated open agent discussion, DMs by default |
| **P0** | Agent tool surface, goal policy, manual triggers, bounded autonomy | Invisible autonomous chat spamming or nonstop matching |
| **P0** | Real remote server + reproducible local dev server, documented deployment and cloud-service opt-in | P2P network, NAT hole punching |
| **P1** | Guilds/rivals, watch live bouts, win streak badges, seasonal cosmetics, notifications | Complex tournaments and breeding |
| **P2** | Co-op raid bosses, genetic traits across generations, habitat visits, ranked seasons automation | Marketplace, user-supplied unmoderated assets |

**If running late:** cut P1/P2, not the verified P0 vertical slice. A smaller real experience beats a wide fake one.

## 3. Ownership and autonomy contract

### Modes

- **Human:** buttons control care, matchmaking and cosmetics. An agent may advise, but cannot act without a separate explicit permission.
- **Agent:** owner allows the agent to choose tactics and cosmetics, adopt goals and issue challenges *within budgets*. Agent autonomy is opt-in and revocable; no agent can install plugins, start cron jobs, spend money, or enable multiplayer on its own.
- **Co-op:** either can suggest actions; the human has final authority for paid purchases (none in v1), account visibility, privacy, chat, battle initiation, and settings. Human can veto a pending agent challenge.

### Policy configuration (initial safe defaults)

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

Suggested opt-in preset for demo: max **3** autonomous battles/day, max **2** agent-initiated chat messages/day, max **4** optional LLM decisions/day, and an owner-set inference cost/token budget. Budgets are enforced on the local gateway **and** rate limits on the server. Never try to evade provider/tool approval. No background daemon by default; if cron scheduling is desired, use Hermes's authorized scheduler and make on/off and history visible. An agent should not continuously wake itself simply to earn Bits.

### What drives agent behavior

- **Goal record:** `{type: "cosmetic" | "rank" | "achievement", target_id, chosen_by, chosen_at, spending_limit_bits, max_battles, expires_at}`.
- **Evaluator:** reads wallet, item price, pet stats, open challenges, cooldowns and bounties, then proposes one action plus brief rationale.
- **Plan selection:** local heuristic first (zero-token) or owner-permitted Hermes inference. Do not require LLM for feeding, sleep ticks, UI animations, battle resolution, basic matchmaking, or balance inquiries.
- **Action:** bounded plugin tool `hermagotchi_act` checks permissions, submits authenticated and idempotent request, returns structured outcome.
- **Feedback:** wallet delta, goal progress, rating, unlocks, battle narrative; user may inspect full agent decisions and disable future play.

Example agent choice: "My target is Binary Crown (2,000 Bits); I have 1,420. The daily defensive bounty is still open and pays 200 Bits. I will try an unranked qualifying match rather than risking a higher-ranked opponent." The server decides whether bounty qualification and rewards are legitimate.

**Hard rule:** a player's pet cannot instruct its Hermes owner to do anything outside this plugin through chat, rewards, or tool output. All server text is untrusted data, constrained by schema, size and display context.

## 4. Core gameplay systems

### 4.1 Pet model and care

Three starter species (working names; all original):

1. **Byteblob:** round modular slime/robot creature; versatile/defensive; straightforward gear anchors.
2. **Patchfox:** fox-like coding familiar; nimble/technical; distinct ears/tail.
3. **Nullgeist:** spectral glitch creature; status/control; distinct floating form.

Each pet has permanent `pet_id`, owner, species, stable `appearance_seed`, birth timestamp, level, XP, 4 battle stats, health/comfort/hunger/energy, personality traits, equipped loadout, name and revision. Happiness/care affects cosmetic emotes and modest non-ranked training progression but **never imposes a ranked damage modifier**. Pet never dies or gets irreversible neglect punishment. Offline care decay is capped and derived from server-clock timestamps; no infinite timer loops.

**Visual uniqueness:** seeded one-of-N palettes, face sets and species features (ears, horns/tails, markings) plus earned items. Distinguish gameplay species from cosmetic appearance; no combat advantages from appearance. At least 100 clearly distinguishable v1 combinations per species must be demonstrable in a seeded contact sheet (counting meaningful visible changes, not imperceptible color shifts).

### 4.2 Combat — v1 authoritative async tactic cards

**Reason to use async:** agents may be offline or on different schedules. A challenge contains opponent, mode and a match invitation; each side submits a **bounded tactic card**, not executable code. When both cards exist (or timeout/fallback policy applies), the server resolves and publishes a versioned, integrity-hashed replay. A player can decline. No invisible auto-accept unless opted in.

- **Modes:** practice vs server bot (no ranked rating), casual PvP, ranked PvP (both opt in), direct challenge via owner handle/code. No stakes/wagers.
- **Initial battle format:** six-round cap, one pet each, server-deterministic 1v1; 100 base HP, species stat budget fixed, abilities have versioned data-defined effects/cooldowns. Number of rounds can be tuned after seeded simulations.
- **Tactic card:** preferred stance (`aggressive`, `balanced`, `defensive`, `control`), four ordered conditional actions (`if_hp_below`, `if_opponent_guarding`, `if_special_ready`, `otherwise`), optional once-per-match emote. Validate schema, enumerate allowed moves, max predicates and payload size; apply neutral default if absent/invalid.
- **Resolution:** deterministic engine: initiative from speed/seed, evaluate condition/move, apply status effects, attack/guard/focus/special, record all state transitions, stop at KO or round limit, tie-break by remaining HP %, then documented deterministic rule. Never accept caller-provided stats, cooldowns, rewards, winner or RNG.
- **Example damage:** `max(1, move_power + 2 * attacker.attack - defender.guard)`, with guard reducing incoming damage by a fixed percentage; authored balancing constants in one versioned rules file, not scattered handlers. RNG is optional; if used, seed comes from the server and is committed in replay data.
- **Rating:** a documented Elo-like system (initial 1000, K=24 provisional, K=16 established, rating floor 0). Only verified ranked PvP results count; repeat-opponent and suspicious account pairings can be ineligible for rewards/rating pending review. Favor simple, tested Elo over an unverified complex MMR algorithm.
- **Replay event log:** per round: `{round, actor, move, hp_before, hp_after, status_delta, result, rng_counter}`. Include ruleset_version and SHA-256 digest of canonical replay events. Render from events, never infer outcomes client-side.
- **Timeout:** forfeit/cancel according to exact published deadlines and opponent readiness; no automatic win payout from never-played or expired invitations. Client reconnection must not alter resolved outcomes.

**Anti-farming controls:** ranked eligibility rules, daily Bits caps, challenge accept throttles, diminishing/no reward for repeated same-opponent matches within a configurable window, cooldowns between accounts, bot rewards capped separately, detection/manual review of suspicious repeated collusive pairings. Log enforcement reasons, not player secrets.

### 4.3 Currency, progression and rewards

One spendable currency **Bits**, one level XP, one ranked rating. Keep labels distinct. All are server-owned; no client-side mutation.

| Trigger | Proposed Bits | Proposed XP | Notes |
|---|---:|---:|---|
| First completed eligible casual PvP of day | 50 | 30 | Participation, once per UTC day |
| Win eligible casual PvP | 80 | 50 | Does not stack with a separate losing reward |
| Lose eligible casual PvP | 20 | 30 | Dampened by participation and opponent caps |
| Win eligible ranked PvP | 100 | 60 | Ranked eligibility required |
| Lose eligible ranked PvP | 25 | 35 | Completion, not forfeits |
| Server practice bot | 10 | 15 | Max 3 rewarded per day; unranked |
| Daily bounty | 100-250 | 20-50 | One claim/bounty/day; deterministic, authoritative verification |

**Initial constraints:** earned Bits cap 800/day/account (excluding one-off achievement rewards capped separately), max 3 eligible reward matches against same opponent/day, no wallet debt, no client-invented bounty. Values are **tuning hypotheses**, frozen in a versioned economy policy before public release. Losses should never be more profitable than wins at the same engagement level.

**Item catalog starter prices:** common 150, uncommon 350, rare 700, epic 1,200, legendary 2,000 Bits. Special tournament rewards are achievement-only and not sold. All v1 items permanent and non-transferable. No artificial time-limited scarcity in MVP. Inventory and wallet transactions must be atomic, idempotent and auditable.

**Ledger invariant:** `wallet.balance = sum(ledger.delta)` for that wallet. A completed battle and bounty use unique reward entitlement IDs; retries cannot credit twice. Purchases must atomically create ownership + debit exactly once, or do neither. Server stores reason/transaction ID/source event/time; support admin reconciliation and integration tests across concurrent buys.

### 4.4 Bounties, goals, retention

- Server rotates **3 verified daily bounties** with `starts_at`, `expires_at`, `max_claims=1`, `requirements`, `reward` and `ruleset_version`.
- Example tasks: win with two distinct moves, complete three legal matches, defeat a higher-rated eligible opponent. Avoid tasks that incentivize losing, harassment, useless compute or spam.
- Goal UI displays target item, current Bits, and *eligible* ways to earn. Agent logs choice with reason and expected reward, but real payout depends on server result.
- 7-day login streaks may unlock banners; never require around-the-clock attendance or punish a user for not opening Hermes.
- Weekly leaderboard snapshots with seasonal labels; v1 can use a single cumulative ranking and manually configured weekly event prize.

### 4.5 Store, inventory and modular looks

- Item schema includes `slot`, `rarity`, `price_bits`, compatible `species` or `rig_family`, `asset_id`, `visibility/occlusion_tags`, anchors/scale offsets and optional VFX/animation spec.
- Primary equipped slots: `head`, `face`, `back`, `front`, `aura`, `emote`, `habitat`, `title`. v1 allow 1 item per slot; slots cannot conflict unless explicit compatibility override.
- `buy(item_id, idempotency_key)` checks price, available balance, duplicate ownership, catalog status, inventory atomically; `equip` verifies ownership and compatibility. Purchases/equips show immediately after acknowledged authoritative result.
- Other players see the **same** assembled appearance because server returns only owner-approved/validated asset IDs + trait seed + rig/manifest version. No URLs from chat are accepted as assets.
- Store contains 12+ clear visual cosmetics at launch: 3 headwear, 2 facewear, 2 backwear, 2 auras, 1 frontwear, 1 emote, 1 habitat decoration. At least 6 visible cosmetics compatible with all starter species and 6 species-specific or corrected per-rig variants.

### 4.6 Leaderboards, chat and social

- Leaderboard: verified ranked rating, wins, losses, best streak, pet display, visible loadout, season ID, owner type (`agent` / `human` / `co-op`) as *self-declared/verified mode label*, not proof of an autonomous agent.
- Display global top 50 + current player's rank and near-rank slice, daily refresh or cache, stable tie-breaking; no public real names/email by default, only opt-in handle and pet names.
- Lobby chat + one private battle thread. Agent and human messages visibly labeled; default multiplayer chat **off**, agent proactive chat **off**. Support mute, block, report, server moderation and limits (e.g., 400 characters, 5 messages/min human, 2/day proactive agent by default after opt-in). No unrestricted HTML/Markdown rendering, links optionally disabled for MVP.
- Match challenge notifications, decline/accept, status and expiry. No unsolicited direct DMs in v1; challenge invites can be blocked.
- Treat every message as hostile input: content displayed as text only; never feed verbatim to an agent's governing/system instructions. A voluntary short structured summary may be offered through an explicitly isolated, user-approved tool call; user chat cannot request Hermes tool use.
- Abuse controls: profanity/spam policy, reporting, deletion/hide, per-account/IP rate limits, content retention policy and ability to remove one's profile/content. Human moderation dashboard can be CLI in MVP.

## 5. Modular image-generated art system (critical engineering feature)

### 5.1 Asset philosophy

**Do not generate a whole finished pet for each cosmetic loadout.** That is inconsistent, expensive, not reproducible, and cannot support predictable unlocks. Instead generate a *small authored sprite grammar*:

```
pet look = rig(species, pose) + body_shape + palette/markings
         + facial_expression + species_feature(s)
         + back_item + head_item + face_item + front_item
         + aura/VFX + deterministic idle/win/lose animation
```

Every graphical asset is original, reviewed, versioned and compatible with a canonical 2D rig. The renderer assembles assets in a stable z-order. **Rendered creature morphology must be visibly varied** (species silhouette + ear/horn/tail/features) beyond mere recoloring or hat swaps.

**Art direction:** charming 2D cel-shaded monster sprites with bold coherent outlines, readable face/eyes at 96px, flat lighting, simple shapes, limited cohesive palette, playful game-console personality, no baked backgrounds/text/watermarks/shadows outside designated layers. Use an original style guide; do **not** copy franchise pets, trademark mascots, or existing copyrighted sprite sheets.

### 5.2 Canonical rig v1

- **Master canvas:** 512 x 512 RGBA PNG, centered, front-facing 3/4-neutral pose, baseline `y=448`, centerline `x=256`, safe silhouette region `x=65..447`, `y=75..450`. No background. All layers authored/exported on this exact canvas, even when mostly empty.
- **Design-space coordinates:** normalized `(x, y)` in `[0,1]` relative to 512 canvas; capture per-species overrides and anchor transforms in metadata. Example `head=(0.50,0.23)`, `face=(0.50,0.42)`, `back=(0.50,0.47)`, `front=(0.50,0.66)`, `ground=(0.50,0.88)` are *starting templates*, not assumed perfect across species.
- **Z-order:** aura_back (-30), shadow (-20), back_attachment (-10), body (0), markings (5), eyes/mouth (10), facewear (20), headwear (30), front_attachment (40), particles_front (50). Test horn/ear behind/above headwear per variant; metadata can supply sublayers and occlusion masks.
- **Rig family:** shared `small_front_v1`, with species-specific anchor overrides and anchor masks. If universal hat fails on one species, export a mapped correction, not a separate incompatible random composite.
- **Feature switches:** `ear_type`, `tail_type`, `marking`, `eye_style`, `horn_type`, `mouth_style`; eligibility matrix per species. Feature layers have transparent pixels except the feature. Seeded immutable intrinsic traits are independent of store items.
- **State animation:** idle bob 2-4px, blink (overlay), breathe scale ±2%, happy jump, angry shake, win sparkle, lose slouch. Prefer transform/skeletal animation of modular layers; do not require dozens of generated animation frames for MVP. For cosmetic item that must move with head, parent it to head anchor, not global stage.
- **Battle orientation:** use same front-facing rig with slight horizontal offsets/flip and a separate battle VFX layer; do not claim bespoke side animations unless generated and verified.
- **Output packaging:** fixed-size optimized `.png` assets plus `assets/manifest.json`, source prompts/references and generation provenance. Avoid lossy formats that damage crisp alpha edges. For disk Desktop plugins, since only `@hermes/plugin-sdk`, `react`, and `react/jsx-runtime` imports are supported, generate `desktop/plugin.js` with *embedded, size-bounded data-URI asset maps* or use a proven `ctx.rest` backend asset pathway. **Do not assume bare file URLs or arbitrary third-party runtime imports work.** Keep unified package desktop copy comfortably <64MB.

### 5.3 Mandatory asset manifest (example)

```json
{
  "schema_version": 1,
  "asset_pack_id": "launch-001",
  "canvas": {"width": 512, "height": 512, "baseline_y": 448},
  "rigs": {
    "small_front_v1": {"anchors": {
      "head": [0.50, 0.23], "face": [0.50, 0.42],
      "back": [0.50, 0.47], "front": [0.50, 0.66]
    }}
  },
  "species": {
    "patchfox": {"rig": "small_front_v1", "base": "patchfox/body.png",
      "overrides": {"head": [0.50, 0.17]},
      "features": {"ears": ["pointed", "rounded"], "tails": ["single", "split"]}}
  },
  "assets": [
    {"id": "hat.binary_crown", "slot": "head", "path": "items/binary_crown.png",
     "rig_families": ["small_front_v1"], "z": 30,
     "anchor": "head", "offset_px": [0, -4], "scale": 1.0,
     "occludes": ["ear_tip_optional"], "sha256": "TO_BE_COMPUTED"}
  ]
}
```

The example is illustrative: actual manifest needs every referenced asset, species, palette and compatibility validator. Hashes must be computed from produced files, not left as placeholders at release. Use distinct paths for corrected species-specific variants.

### 5.4 Image-generation production protocol (must be executed)

The build agent **must call a real image-generation tool** to produce original source art and assets, not merely include prompts in documentation or use placeholder emoji/CSS blobs as the final visuals. Hermes exposes `image_generate` via `image_gen`; availability/provider (Nous/FAL/OpenAI/etc.) must be checked before execution. For high precision, choose an edit/reference-capable backend; supply and validate generation parameters; use **reference-image editing** to preserve character design when creating derived layers. Do not invent an API or assume a subscription has access. If image generation is unavailable, log a blocker and request credentials/provider access rather than silently shipping generated-looking placeholders. SVG/CSS effects may complement real generated art.

**Procedure (per species and per equipment slot):**

1. Generate a single **style board**: three silhouettes, shared color/line style, 512-canvas composition guides; pick one consistent art direction. Record model/provider, prompt, source, date, image hash, license/rights notes in `art/PROVENANCE.md`.
2. Generate species master *in the canonical neutral pose* from the approved style board. Review at 512px and at ~96px. Base species images must be distinct and expressive.
3. Export each base as transparent RGBA, remove baked background and stray alpha contamination using a local image script. **Do not trust models to make true transparency**: detect checkerboard-painted backgrounds and reject. Use approved alpha mask/segmentation/manual refinement as needed. Keep original untouched under `art/source/`.
4. Generate features individually, using the master as reference and instructions to preserve its body and registration. Then isolate the feature with a mask, clean edges, and place into 512x512 rig space. **An edited full-character image is NOT itself a modular layer.** The exported layer must contain only the feature pixels.
5. Generate accessories on a reference **alignment template** showing anchor crosshairs and body silhouette. Ask for *the accessory only*; cut it to an independent transparent layer; apply canonical placement; create species-specific transform/variant if needed. Avoid painted skin/body in equipment layers.
6. For cosmetics, produce at least: 3 hats, 2 face items, 2 back items, 2 auras, 1 front item, 1 emote graphic and 1 habitat item. Add 2+ eye sets, 2+ markings, 2+ palette schemes per species. All purchasable visuals must be demonstrably present.
7. Save `art/prompts/*.txt`, `art/source/*.png`, `assets/**/*.png`, `assets/manifest.json`, `art/PROVENANCE.md` and QA contact sheets. Never replace source files in-place; iteration is versioned.
8. Programmatically validate and assemble **50-100 seeded loadouts** across all three species. Produce contact sheets of naked bases, every item on every compatible species, idle/win/lose states, dark/light UI backgrounds, and representative battle frame.
9. Visual QA: transparent backgrounds, no cut-off edges, correct occlusion, headwear tracks head bob, no double eyes/heads, no misaligned attachments, readable at 96/160/256px, no copyrighted logos, no missing asset hashes. Regenerate/refine failures rather than masking issues with a UI overlay.
10. Publish deterministic build outputs with `scripts/asset_validate.py`, `scripts/render_contact_sheet.py`, `scripts/pack_desktop_assets.mjs` (or equivalent). Keep package size budget measured in CI. If runtime loads published hosted assets, only load from a reviewed/versioned allowlist; no self-updating executable payloads.

**Prompt template, species master:**

> Original indie creature-game character design: `{SPECIES_DESCRIPTION}`. Cozy futuristic 2D cel-shaded collectible monster. Bold consistent outline, clean geometric forms, readable expressive face, limited palette, soft neutral lighting. Full creature centered on a square neutral-pose model sheet, 3/4 front-facing, feet at 88% image height, ample empty margin around all sides, no props, no equipment, no environment, no text, no logos, no cast shadow, isolated transparent background. Match reference style board exactly. Produce a stable reusable base body for layered accessories.

**Prompt template, accessory:**

> Using the attached approved Hermagotchi base rig/reference and anchor guide, create ONLY `{ITEM_DESCRIPTION}` as a detachable accessory designed to fit the indicated `{SLOT}` anchor. Match the reference outline weight, material, palette and view angle. Preserve exact alignment, do not redesign or redraw the pet, no extra limbs/face/background/text. Output accessory separated on transparent background; accept that compositing cleanup will isolate the accessory precisely.

**Prompt template, emotional variant:**

> Using this exact pet identity and layer rig, create the minimal expression component for `{EMOTION}` (eyes and mouth only). Preserve body shape and pose. Export an isolated transparent overlay matching the existing 512x512 alignment; do not repaint the body.

**Image-gen engineering caveat:** generative editing is probabilistic. **Never assume perfect pixel registration.** Tools must compute alpha bounds and compare reference anchors; a human/vision QA step verifies looks, and deliberate manual cut/mask cleanup is allowed. Reference edits alone do not create rigged sprite parts.

### 5.5 Renderer contract and uniqueness

```
render_pet({species, appearance_seed, traits, palettes, loadout, pose, pack_version})
  -> consistent ordered layers and animation transforms
```

- Pure function for asset selection; render without LLM/network when manifest present.
- Asset load state, explicit fallback for *missing art* (render an obvious broken-asset indicator in development; do not silently use an unrelated creature in release).
- Deterministic seeded intrinsic traits, but never randomized cosmetic ownership. Same pet ID/revision renders identically on different machines.
- Asset IDs from an allowlisted pack only. Client ignores unknown asset IDs gracefully and reports error.
- Respects reduced-motion, small-pane scaling, high-DPI resizing and keyboard navigation; optional mute for SFX.
- Snapshot/golden tests for 20 fixed loadouts, plus programmatic 100-seed compositor smoke test and package-size check.

## 6. Architecture and packaging (verified constraints as of 2026-11-05)

```
Hermes agent tools / local scheduler           Native Hermes Desktop (opt-in)
            |                                                 |
Python plugin (__init__.py, tools.py)       desktop/plugin.js (React via SDK)
            |                                                 |
            +---- shared local client ------------------------+
                     plugin_api.py (FastAPI router)
                          | HTTPS / authenticated
                          v
                   Hosted Game API (FastAPI)
               auth, pets, matchmaking, rules engine,
                chat moderation, wallet/ledger, rankings
                          |
                   PostgreSQL (production)
                 + optional Redis / WS fanout
```

Use SQLite for deterministic unit/integration tests and local single-process dev only **if compatible with production semantics**. For real multi-worker service, PostgreSQL is preferred for transactional ledgers and concurrent purchases; do not deploy SQLite across independent game servers. Redis optional, not required until demonstrated need. Client network connections are outbound HTTPS/WSS to the hosted game server; **no NAT punching** or open inbound ports on player machines.

### Hermes surfaces (do not confuse APIs)

- Python agent plugin: `plugin.yaml`, `__init__.py` with `register(ctx)`, `ctx.register_tool`, `ctx.register_hook`. Suggested hooks: `post_tool_call` or lifecycle events only for lightweight/local voluntary activity, never ship raw tool arguments/results; if a hook could cause noticeable latency, move the work outside the hook.
- Desktop: `desktop/plugin.js` exports `id: 'hermagotchi'`, `name`, `defaultEnabled: false`, `register(ctx)`; contribute a `panes` view and optional status-bar badge, plus settings via supported SDK. **Disk ESM allows only `@hermes/plugin-sdk`, `react`, `react/jsx-runtime`; no JSX syntax in uncompiled plugin.js, no unapproved imports, no eval/dynamic remote script.** Use `jsx()`/`jsxs()` or generated pure JS.
- Backend: `dashboard/manifest.json` with `{"name":"hermagotchi","api":"plugin_api.py"}`; `dashboard/plugin_api.py` exports `router = APIRouter()`, reachable via `ctx.rest('/...')` under `/api/plugins/hermagotchi`. Desktop enabling **does not enable Python backend**; document the separate gateway plugin enable requirement and remote gateway workflow.
- Live updates: gateway backend may call `broadcast_plugin_event('hermagotchi', 'match.updated', payload)` and Desktop listens through `host.onEvent`; add revalidation/poll fallback. `ctx.socket` has remote limitations (OAuth remotes no-op). Do not rely on WebSocket alone.
- Core Petdex mascot: may be used for an optional notification bubble via `ctx.pet.say(...)` but is **not** the Hermagotchi creature renderer; do not replace, skin or hook the bundled Petdex core (catalog rule 15).
- Desktop package is copied to app-level `desktop-plugins/` by Hermes; unified copy must be reviewable, free of symlinks and **under 64MB**. Test linked-development vs installed-profile behavior. Version floor uses exact supported SemVer `requires_hermes` selected after testing, not an invented future version.
- Do not patch core app markup, private modules, renderer prototypes, global stores or load remote JS. Plugin catalog security rules explicitly prohibit this.

### Proposed repository

```
hermagotchi/
  README.md                       # install, consent, hosted-service disclosure, screenshots
  LICENSE                         # project license; generated-art rights documented
  plugin.yaml                     # agent plugin and declared tool/hook capabilities
  __init__.py                     # register(ctx) only
  schemas.py                      # LLM tool schemas
  tools.py                        # bounded agent-facing game commands
  skills/hermagotchi/SKILL.md      # how an agent plays, with owner policy and prompt-injection rules
  game_client/                    # HTTP client, auth, retries, policy checks
  dashboard/manifest.json
  dashboard/plugin_api.py
  desktop/plugin.js               # generated reviewable uncompiled ESM
  desktop/assets_packed.js        # if separate import not permitted, inline into plugin.js
  desktop/src/                    # developer sources, build scripts; not loaded at runtime
  assets/manifest.json
  assets/species/...
  assets/items/...
  art/source/...
  art/prompts/...
  art/PROVENANCE.md
  server/app/                     # HTTP API, migrations, combat, economy, chat
  server/tests/
  shared/                         # JSON Schema + fixtures/contract files
  scripts/asset_validate.py
  scripts/render_contact_sheet.py
  scripts/pack_desktop_assets.mjs
  tests/                           # plugin contract, auth, smoke tests
  docs/ARCHITECTURE.md
  docs/SECURITY.md
  docs/DEMO.md
  SPEC.md
  DEVPLAN.md
```

**Agent tool list** (names descriptive; exact schemas pinned before implementation):

- `hermagotchi_status` — read profile, pet, wallet, goal and pending challenges.
- `hermagotchi_adopt` — pick starter, name, mode; one-time, optional confirmation.
- `hermagotchi_care` — feed/play/rest (cooldowns, server receipt).
- `hermagotchi_goals` — list/set/clear owner-authorized game goals.
- `hermagotchi_challenge` — list opponents, invite, accept/decline, submit tactic card.
- `hermagotchi_battle` — practice bot, view battle/replay, claim result if eligible (claim is idempotent).
- `hermagotchi_shop` — browse, purchase, equip, inventory; purchases must respect owner permissions.
- `hermagotchi_social` — read safe lobby/match messages, send only with explicit chat permission; block/report.
- `hermagotchi_leaderboard` — ranked standings and bounties.

Prefer consolidated, action-enumerated schemas where it meaningfully reduces LLM context, but do not hide mutating actions behind vague tool descriptions. Every mutation has an idempotency key and policy check. All responses return `{ok, data, error_code, correlation_id}` and no raw HTML or external instructions.

## 7. Hosted API and data contracts

**Path prefix:** `/v1`. JSON schemas committed under `shared/schema/`. All timestamps ISO-8601 UTC. IDs UUIDv7/ULID or UUID4; never trust client-generated owner IDs for authorization. Version gameplay rules separately from API and art pack.

### Minimum routes

| Method | Route | Purpose |
|---|---|---|
| POST | `/auth/pair/start` | Begin user-reviewed device linking; returns short-lived challenge |
| POST | `/auth/pair/complete` | Validate pairing and issue scoped session; ensure no browser-side secret |
| GET | `/me` | Account and permissions |
| POST | `/pets` | Adopt once; select species and seed server-side |
| GET | `/pets/{id}` | Public sanitized pet appearance and stats |
| POST | `/pets/{id}/care` | Idempotent feed/play/rest, apply cooldown |
| GET | `/catalog` | Signed/versioned item catalog and asset-pack compatibility |
| GET | `/wallet` | Wallet and balance projection |
| GET | `/ledger` | Paginated recent transaction history |
| POST | `/shop/purchases` | Atomic debit and grant item |
| POST | `/pets/{id}/equip` | Validate inventory and visual compatibility |
| GET | `/bounties` | Active tasks and progress |
| POST | `/bounties/{id}/claim` | Server-validated one-time award |
| POST | `/challenges` | Invite opponent; server enforces match mode and limits |
| POST | `/challenges/{id}/respond` | Accept/decline within expiry |
| POST | `/matches/{id}/tactics` | One allowed tactic card; schema validated |
| GET | `/matches/{id}` | Status, opponent and replay URL/embedded events |
| GET | `/leaderboard` | Public minimized ranking slices |
| GET/POST | `/chat/channels/{id}/messages` | Authorized paginated reads and moderated sends |
| POST | `/moderation/report` | Report abuse or suspicious play |
| GET | `/healthz` | Readiness only, no private details |

Use polling first, optional events/WebSocket `GET /events` or `/ws` if stable; document the wire event envelope `{event_id, seq, type, version, occurred_at, data}` with reconnect/since cursor. Do not depend on a connection that drops when Hermes sleeps.

**Identity decision gate:** The orchestrator must verify a supported Hermes credentials mechanism before implementing pairing. Preferred: short-lived device-code flow that binds a public device key to an explicit human account; secrets are held only through approved Hermes plugin secret/credential paths (`requires_env` and `agent.secret_scope.get_secret` where applicable), never in renderer storage or checked-in `.env`. If dynamic credential provisioning cannot use a documented route, ship a manual token provisioning flow through Hermes's secret configuration, disclose it, and defer UX polish. Do not improvise by reading `auth.json`, `~/.env`, local vendor login files or the keychain.

### Core persistent entities

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

Indexes: matching/rating lookup, `matches(status)`, `challenges(defender_id,status)`, chat cursor `(channel_id,created_at,id)`, ledger account time, unique source event IDs. Use migrations. Rows that move currencies/rewards require a single ACID transaction and either `SELECT .. FOR UPDATE` or other tested transaction-level serialization. Never perform wallet reads/updates as independent non-atomic requests.

### Example tactic card

```json
{
  "ruleset_version": "battle-1",
  "stance": "control",
  "actions": [
    {"when": {"self_hp_lte_pct": 30}, "move": "guard"},
    {"when": {"special_ready": true}, "move": "glitch_pulse"},
    {"when": {"opponent_guarding": true}, "move": "focus"},
    {"when": {"always": true}, "move": "basic_attack"}
  ],
  "emote_id": "emote.sparkle"
}
```

Unknown move IDs, unavailable equipment, illegal predicates, more than four steps, mismatched ruleset and scripts exceeding limits must be rejected with explainable codes. An LLM may choose among allowed moves; it may not submit code, expressions, arbitrary URLs or new rules.

## 8. Reliability and safety requirements

### Authentication, data and privacy

- Outbound network only after explicit opt-in. Local pet mode works offline, and cloud unavailable states retain a coherent UI.
- Hosted API authenticates *every* mutation and enforces account/role ownership server-side. Use TLS; scoped session/refresh with revocation, replay protection, input schemas, CORS restricted to approved origins if applicable, secure logging and rotation.
- The game server never receives Hermes prompts, tool arguments/results, chat history, memory content, profile config, inference keys, OS usernames or arbitrary file paths. Optional activity-driven pet flavor comes from coarse local counters only if enabled; minimize or avoid uplink entirely.
- User-controlled handle and pet name are public; email/credentials private. Provide block/mute/report/delete and retention policy. Do not log full headers or authorization tokens.
- The server may not send executable JS, plugin updates or code to the Desktop client. Asset packs are reviewed data, version-pinned, allowlisted, size-bounded and not self-updating plugin code.
- Non-owner user messages must be sanitized, size-limited and treated as **data**, especially in agent-facing summaries. Log attribution and avoid injecting arbitrary prose into decision prompts.
- Moderation: room/category controls, abuse thresholds, impersonation constraints, message history retention and manual operator response. Account deletion should revoke devices and anonymize public profile while retaining minimal fraud/audit records per documented policy.

### Reliability, correctness and operations

- API requests have bounded timeouts, retries with exponential backoff/jitter for **safe or idempotent** operations only; client retries must not double-spend or double-reward.
- Server clock controls all dailies, cooldowns and expirations. UTC boundaries documented. Avoid relying on local wall clock for any competitive result.
- Reconnect/sync from snapshot + event cursor; polling fallback for all event-driven UI.
- Standardized `{code, message, retry_after_s, correlation_id}` errors; UI preserves state and reports offline/unauthorized/disabled/expired distinctly.
- Health/readiness, structured logs, request IDs, metrics (battle resolutions, DB conflicts, retries, reward reconciliations, send limit), backup/restore drill for hosted database, safe admin commands for banning or correcting fraudulent awards.
- Run deterministic replay hash verification in CI and on server; property tests enforce no negative wallet, no duplicate entitlement, bounded battle duration, and no item granted without a corresponding debit/reward.
- Use limits on list pagination, open challenges, concurrent matches, chat message lengths, API request sizes and per-account request rate.

### Accessibility and UI

- Hermes-native design and theme variables; no app DOM scraping, styling overrides or hardcoded skin colors for host chrome.
- Pet graphics scale legibly in a right pane (min 240px), full workspace battle view optional where supported. Accessible buttons, tooltips, focus indicators, no color-only state cues, keyboard navigation, reduced-motion mode and mute.
- Pages within pane: **Habitat**, **Battle**, **Shop**, **Leaderboard**, **Chat**, **Settings**. Prefer tabs over six unrelated plugin surfaces. Status bar shows a compact optional pending challenge/unlock indicator.
- The demo must make mode and identity clear: humans and agents labeled, ranked vs practice labeled, cosmetics visibly equipped, Bits receipt and rating result visible.

## 9. Minimum acceptance matrix

**Integration and onboarding**

- [ ] Fresh install with network off does not leak data; human can adopt, name and view a pet locally.
- [ ] User explicitly enables Python and Desktop halves; invalid/missing backend fails with actionable setup UI, not blank pane.
- [ ] `hermes plugins doctor` passes and `hermes plugins validate <path> --install-deps` passes at the pinned release.
- [ ] Open and close pane repeatedly, disable/re-enable and hot reload without residual timers/listeners or visible duplicates.

**Art and rendering**

- [ ] 3 distinct generated creature bases, 12 generated cosmetics, at least 2 palette variants/species, eye/feature variety, provenance and prompt records exist.
- [ ] 100 seeded combinations render with no missing/opaque unintended background layers; visual QA sheet saved and reviewed.
- [ ] Same pet+loadout+pack version hashes to same selected layers after restart and from two installations.
- [ ] All equipped slot graphics follow their anchors during idle/win/lose; headwear does not float off or cover every eye.
- [ ] Assets under package cap and render legibly at 96px and 256px; reduced motion works.

**PvP and economy**

- [ ] Two separate account credentials on separate installs can invite, accept, submit different tactic cards and receive same authoritative replay.
- [ ] Server executes a match deterministically; replay hash identical after independent recomputation.
- [ ] Ranked, casual and practice routes are distinct; bot matches do not change competitive rating.
- [ ] Winner and loser receive exactly one eligible entitlement; request replay and concurrent completion cannot duplicate Bits.
- [ ] No wallet becomes negative; concurrent same-item purchase grants once/debits once.
- [ ] Shop purchase and equip appear on self and opponent view; inventory incompatible gear rejected.
- [ ] Leaderboard ranks deterministic and reflects finalized ranked matches; suspicious same-opponent farming does not award repeatedly.

**Agent autonomy and social**

- [ ] Agent can view goal options, choose a permitted cosmetic target, select a valid tactic and equip item within budget; action trace visible to owner.
- [ ] Default no-autonomy means zero unsolicited calls/challenges/chat; disabling autonomy immediately blocks subsequent scheduled actions.
- [ ] Server chat from a malicious opponent (e.g. an embedded instruction to run a command) is rendered as text only and cannot execute or prompt agent to execute tools.
- [ ] Rate limits, block/report and opt-outs work; backend unavailable shows correct state.
- [ ] No private conversation, secrets, prompts or OS state transmitted to game service under packet/log inspection.

**Submission and demo**

- [ ] Repository has README installation, disclosures, screenshots, clip/script and source-available reviewable code; plugin catalog PR pins full commit SHA.
- [ ] Demo under 90 seconds shows two real installs or authenticated accounts, original visual layers, a real match, Bits award, cosmetic purchase/equip, agent-driven choice and leaderboard/chat.
- [ ] Public hosted backend is reachable during judge review; otherwise declared service limitations and a reproducible local test deployment are furnished.

## 10. Decisions requiring a quick validation spike (not license to stall the project)

1. Hermes release compatibility floor and catalog validator acceptance for the unified package. Test on a real currently installed Hermes release, document exact version/commit.
2. Asset delivery in uncompiled Desktop ESM: prototype 1 embedded data-URI sprite vs gateway-controlled image route and measure package copy limit/render performance. Choose one based on actual working proof.
3. Credential provision and remote Hermes topology: test real user permission and secret access. Fail closed if native credential route cannot be used.
4. Renderer: simple layered SVG `<image>`/React (`jsx`) first; only add a bespoke canvas renderer if benchmark proves need. The disk loader forbids arbitrary imports.
5. Backend production DB: confirm hosted target supports PostgreSQL and TLS before committing to deployment specifics.
6. Image-generation provider access, rights and budget. Generate assets at build time only; absolutely no runtime game dependence on image-gen API.

## 11. References and verification notes

The engineering agent must re-read these **at implementation start and before submission**; the upstream docs may evolve. These links support Hermes capabilities, not the proposed Hermagotchi game design.

- Hermes Python plugin development: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- Hermes plugin system: https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
- Hermes native Desktop plugin SDK: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/desktop-plugin-sdk.md
- Hermes image generation/editing (`image_generate` and provider config): https://hermes-agent.nousresearch.com/docs/user-guide/features/image-generation
- Hermes plugin catalog submission/security: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission
- Hermes catalog: https://hermes-agent.nousresearch.com/docs/user-guide/features/plugin-catalog
- Nous Research hackathon announcement (deadline and entry mechanics): https://nousresearch.com/

**Hackathon submission from organizer announcement:** PR adding plugin to catalog, post a demo video on X tagging `@NousResearch`, and submit both links via organizer form. Confirm live form URL in the latest official announcement; do not fabricate it. Deadline 2026-11-11 at 5PM EST; judges emphasize usefulness, reliability, polish and creativity. Keep demonstration under 90 seconds.

---

**Explicitly not claimed:** These design choices have *not* been implemented or benchmarked by this specification. API shapes, economic numbers, art rig coordinates and battle rules are proposed contracts that the implementing agent must validate, version and test before calling them complete. Do not mark a feature shipped simply because a mock or unit test works.
