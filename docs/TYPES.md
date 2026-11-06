# Hermagotchi Types — `battle-2`

Status: hackathon type chart + passives for ruleset **`battle-2`**.  
`battle-1` replays stay valid and ignore type entirely.  
Implementation: `server/app/combat/types.py`, wired through `engine.py` / `validation.py`.  
Balance eval: `evals/type_balance.py`.

## Design goals

1. Exactly **five** types with equal offence and defence (no dominant strategy from the chart alone).
2. Theme fit for a hacker / AI-agent pet game.
3. Mild multipliers so a 6-round, 100 HP bout remains interactive.
4. Same-type attack bonus (STAB) without making coverage worthless.
5. One modest passive per type, not a second hidden type chart.
6. Deterministic, integer-only math (no floats) so replays hash stably.

## Research summary (best practice)

| Practice | Source | How we apply it |
|---|---|---|
| Start with equal advantages / disadvantages (RPS loops) | [r/gamedesign type-chart thread](https://www.reddit.com/r/gamedesign/comments/4zacn0/designing_type_effectiveness_chart_in_my/); [GameDev.SE — organize type advantages](https://gamedev.stackexchange.com/questions/207045/how-should-i-organize-the-type-advantages-and-disadvantages-for-my-monster-catch) | Symmetric 5-cycle: each type beats 2, loses to 2 |
| Odd-\(n\) tournaments are the only perfectly fair pure RPS | [Rock, Papers, Scissors and beyond (molab)](https://molab.marimo.io/notebooks/nb_5AqxB9MfasrxQ8SjVmAbsH) | \(n=5\), \(k=(n-1)/2=2\) |
| Row/column sums should match for chart fairness | [Pokémon VG Type Info](https://pokemonaaah.net/research/vg/typeinfo/); matrix advice in the gamedesign thread | Every type has equal offensive/defensive chart score |
| Simulate meta convergence toward uniform Nash | GameDev.SE spreadsheet / mobility model; [Julien et al., balancing zero-sum games](https://www.cs.cornell.edu/~ajul/zerosum/zerosum.pdf) | `evals/type_balance.py` runs seeded real-engine battles |
| Pokémon main series: SE \(2\times\), NVE \(0.5\times\), STAB \(1.5\times\) | [Bulbapedia Damage](https://bulbapedia.bulbagarden.net/wiki/Damage); [STAB](https://bulbapedia.bulbagarden.net/wiki/Same-type_attack_bonus); [Pokémon DB type chart](https://pokemondb.net/type) | Baseline reference — too swingy for 6 rounds |
| Shorter formats + seeded variance softens hard counters | [Pokémon GO milder SE/STAB](https://www.reddit.com/r/pokemongo/comments/58hlsr/super_effectivestab_balance_is_killing_diversity/); Kyle ask 2026-11-05 | SE/STAB \(17/16\) + flat \(\pm 5\) seed variance → ~61% SE wins |
| Keep overlapping loops; avoid isolated triangles | r/gamedesign + JourneyMon type-chart devlog | One fully connected pentagon, not five isolated pairs |
| Species rarity / role still matter even if the chart is fair | r/gamedesign | Species stats stay on the shared budget; types alone are balanced in the eval |

## The five types

Clockwise order (attacker beats the next two):

`signal → kernel → payload → firewall → glitch → (signal)`

| Type | Theme | Passive (`id`) | Attack flavour | Example move names (flavour; not all wired yet) |
|---|---|---|---|---|
| **signal** | Broadcast, ping, jam, RF / messaging | `ping` — +1 effective speed | Interrupt, carrier, noise | `ping_burst`, `carrier_wave`, `noise_floor` |
| **kernel** | Syscalls, privilege, OS / hardware core | `rootkit` — +1 focus stat | Privilege, panic, syscall | `syscall_spike`, `privilege_escalation`, `kernel_panic` |
| **payload** | Inject, overflow, offensive code | `zero_day` — first damaging hit +1 raw | Shellcode, smash, ROP | `shellcode`, `buffer_smash`, `rop_chain` |
| **firewall** | Block, quarantine, perimeter policy | `hardened` — first incoming hit −1 dmg (min 1) | Drop, quarantine, TLS | `packet_drop`, `quarantine`, `tls_handshake` |
| **glitch** | Corrupt, desync, undefined behaviour | `undefined` — while HP ≤ 30%, +1 attack | Segfault, heap, UB | `segfault_pulse`, `heap_spray`, `undefined_behavior` |

### Matchup rationale (theme)

- **signal** jams **kernel** scheduling and detects / interrupts **payload** in transit.
- **kernel** sandboxes **payload** and can rewrite **firewall** rules from root.
- **payload** pierces **firewall** policy and weaponises **glitch** states.
- **firewall** filters **glitch** noise and rate-limits **signal** floods.
- **glitch** corrupts **signal** channels and panics **kernel**s.

## Type chart

Rows = attack type, columns = defender type. Values are damage multipliers.

| atk \ def | signal | kernel | payload | firewall | glitch |
|---|---:|---:|---:|---:|---:|
| **signal** | 1 | **17/16** | **17/16** | 16/17 | 16/17 |
| **kernel** | 16/17 | 1 | **17/16** | **17/16** | 16/17 |
| **payload** | 16/17 | 16/17 | 1 | **17/16** | **17/16** |
| **firewall** | **17/16** | 16/17 | 16/17 | 1 | **17/16** |
| **glitch** | **17/16** | **17/16** | 16/17 | 16/17 | 1 |

Mirror property: if A is SE vs B then B is NVE vs A (and vice versa). Same-type is always neutral \(1\times\) before STAB.

### Multipliers (integer fractions)

| Modifier | Fraction | Decimal | Notes |
|---|---|---:|---|
| Super-effective | \(17/16\) | 1.0625 | Mild; pairs with flat variance |
| Not very effective | \(16/17\) | ≈0.941 | Mild |
| Neutral | \(1/1\) | 1.0 | |
| STAB | \(17/16\) | 1.0625 | Applied when move type == attacker type |
| SE + STAB | \(289/256\) | ≈1.129 | |
| NVE + STAB | \(1/1\) | 1.0 | Resisted STAB lands as neutral |
| Damage variance (`battle-2`) | flat ±5 | — | Seeded per hit from battle RNG stream |

Formula (battle-2 attacks only):

```text
raw = max(1, power + 2*atk - guard [+ focus] [+ zero_day])
damage = guard_reduce(raw)
damage = max(1, damage * type_num // type_den)
damage = max(1, damage * stab_num // stab_den)   # if STAB
damage = max(1, damage - 1)                      # if firewall hardened pending
damage = max(1, damage + variance)               # variance in [-5, +5] from seed
```

## Move typing in `battle-2`

| Move | Type |
|---|---|
| `basic_attack`, `quick_strike`, `glitch_pulse` | inherit attacker type (STAB) |
| `guard`, `focus`, `recover` | untyped (no multiplier) |

A universal glitch-typed special was tried and rejected: it let every type punch
`signal`/`kernel` for free and broke overall 50% balance. Per-type signature
moves can arrive in a later ruleset without invalidating `battle-2` mirrors.

Pets without an explicit `type` field use the species → type map below. An optional `type` override on the pet dict is accepted only under `battle-2` (for sims / future dual options); `battle-1` ignores it.

## Species → type mapping

Launch-003 ships **10** playable species (2 per type). Starter combat budgets for
`byteblob` / `patchfox` / `nullgeist` are unchanged from `battle-1`.

| Species | Type | Notes |
|---|---|---|
| `cachebat` | signal | hovering cache/network bat |
| `daemowl` | signal | daemon owl, lightning chest |
| `byteblob` | kernel | starter robot-slime |
| `kernelcrab` | kernel | chip-shell crab |
| `patchfox` | payload | starter coding fox |
| `shellsnail` | payload | terminal-shell snail |
| `stacktoise` | firewall | server-rack tortoise |
| `firewyrm` | firewall | fire-wall pun dragon |
| `nullgeist` | glitch | starter glitch ghost |
| `regexopus` | glitch | asterisk-spotted octopus |

## Balance targets

From `evals/type_balance.py` (equalised `byteblob` chassis, forced types, **varied**
tactic decks/stances, many seeds):

| Metric | Target | Measured (120 seeds / 3000 battles) |
|---|---|---|
| Per-type overall win rate | \(50\% \pm 3\%\) | signal 48.2, kernel 49.4, payload 50.5, firewall 50.4, glitch 51.5 |
| SE pairwise A-win | \(60\%\)–\(70\%\) | **60.9%** |
| Mirror matchup A-win | \(45\%\)–\(55\%\) | **50.0%** |
| Chart row/column score equality | exact | exact |

### Softening hard counters (Kyle-approved, 2026-11-05)

`battle-1` stays byte-identical (no damage variance). `battle-2` draws a
deterministic flat modifier in \([-5,+5]\) per attack from the committed seed
stream (same RNG as initiative), stored on the event as
`status_delta.damage_variance`. Mild \(17/16\) SE/STAB plus varied decks keep
type advantage meaningful without 100% SE lockouts.

## Ruleset versioning

| Ruleset | Types? | Passives? | Default for live matches |
|---|---|---|---|
| `battle-1` | no | no | yes (current) |
| `battle-2` | yes | yes | opt-in / practice until economy migration |

`normalize_ruleset` accepts both. Tactic cards must declare the matching `ruleset_version`. Missing cards become the neutral default for that version.

## Open questions

1. When should matchmaking default to `battle-2`? (Recommend after art ships ≥1 species per type.)
2. Dual-typing later? Chart is single-type only; dual would need a new ruleset (`battle-3`) to keep replays stable.
3. Should `glitch_pulse` stay universally glitch-typed, or become a per-type special catalogue?
4. Pet adopt API still enumerates the original 3 starters until a follow-up widens `/pets` — combat already accepts all 10.

## Test / eval commands

```sh
python3 -m pytest -q server/tests/test_combat_engine.py server/tests/test_combat_types.py
python3 evals/type_balance.py
python3 evals/measure_schemas.py   # expect o200k_base total unchanged at 933 if no schema edits
```
