# Hermagotchi Combat — `battle-1`

Status: wave-1 pure engine + wave-hackathon `battle-2` types. Authoritative,
deterministic, and intentionally separated from HTTP, wallets, ledgers,
rewards, ratings, and persistence. Type chart details live in `docs/TYPES.md`.

Implementation: `server/app/combat/`
Tests: `server/tests/test_combat_engine.py`
Golden replay: `server/tests/fixtures/replays/battle-1_patchfox_vs_byteblob_seed42.json`

## Entry point

```python
from server.app.combat import resolve_match

replay = resolve_match(
    "battle-1",
    {"species": "patchfox"},
    {"species": "byteblob"},
    tactics_a,
    tactics_b,
    42,
)
```

`resolve_match(ruleset, pet_a, pet_b, tactics_a, tactics_b, seed)` returns a
`Replay`. Callers provide only identity/species, bounded tactic cards, and the
server seed. The engine derives all combat stats, damage, order, winner, and
replay hash. Caller-supplied stats, cooldowns, winners, damage, or rewards are
neither accepted nor consulted.

`ruleset` may be the string `"battle-1"`, the exported `BATTLE_1` / `RULESET`
object, or a mapping with `ruleset_version` / `version` equal to `"battle-1"`.
Any other version is rejected.

Pets are mappings or objects with a `species` attribute. Only the species is
used. Appearance, care, equipment, level, and stats never modify `battle-1`
ranked damage.

A missing card (`None`) becomes the neutral default. A malformed card is
rejected with a typed code; it does not silently become the default.

## Constants

| Constant | Value |
|---|---:|
| Ruleset version | `battle-1` (default) / `battle-2` (types + passives) |
| Base / max HP | 100 |
| Round cap | 6 |
| Stat budget | 20 per species |
| Guard move reduction | 40% |
| Focus charge cap | 2 |
| Focus bonus base | 2 |
| Recover heal | 10 |

### Species

| Species | HP | Attack | Guard | Speed | Focus | Budget |
|---|---:|---:|---:|---:|---:|---:|
| `byteblob` | 100 | 6 | 6 | 4 | 4 | 20 |
| `patchfox` | 100 | 7 | 3 | 7 | 3 | 20 |
| `nullgeist` | 100 | 5 | 4 | 5 | 6 | 20 |

Byteblob is durable and balanced, patchfox is fast and aggressive, nullgeist
is a slower control/special species.

### Stances

Stances modify effective stats for the whole match. Attack cannot drop below
1, guard and speed cannot drop below 0.

| Stance | Attack | Guard | Speed |
|---|---:|---:|---:|
| `aggressive` | +2 | -1 | +1 |
| `balanced` | 0 | 0 | 0 |
| `defensive` | -1 | +3 | -1 |
| `control` | -1 | +1 | +2 |

### Moves

All moves are available to every species. Cooldowns count full rounds in
which the move cannot be used again.

| Move | Kind | Power | Cooldown | Notes |
|---|---|---:|---:|---|
| `basic_attack` | attack | 8 | 0 | standard damage |
| `quick_strike` | attack | 5 | 1 | pierces the guard move reduction |
| `guard` | guard | — | 0 | 40% incoming reduction this round |
| `focus` | focus | — | 0 | +1 charge, max 2 |
| `glitch_pulse` | attack | 14 | 2 | special; spends all focus charges |
| `recover` | heal | — | 3 | heals 10, capped at max HP |

## Tactic card

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

Rules:

- Maximum 4 actions, evaluated in order. The first matching action is used.
- If no action matches, the engine uses `basic_attack`.
- Allowed stances: `aggressive`, `balanced`, `defensive`, `control`.
- Allowed moves: the six moves in the table above.
- Allowed predicates: `self_hp_lte_pct`, `opponent_guarding`,
  `special_ready`, `always`.
- Each `when` contains exactly one predicate.
- `self_hp_lte_pct` is an integer from 0 to 100 inclusive.
- `opponent_guarding` and `special_ready` are booleans.
- `always` is a boolean.
- `emote_id` is optional and must match `emote.<name>` using letters, digits,
  underscore, dot, or hyphen, at most 64 characters.
- Unknown top-level fields, unknown action fields, scripts, expressions, and
  URLs are rejected.

### Neutral default

```json
{
  "ruleset_version": "battle-1",
  "stance": "balanced",
  "actions": [
    {"when": {"always": true}, "move": "basic_attack"}
  ]
}
```

### Validation codes

| Code | Meaning |
|---|---|
| `tactic_not_object` | card is not an object |
| `tactic_field_unknown` | unknown top-level field |
| `tactic_ruleset_mismatch` | card ruleset is not `battle-1` |
| `tactic_stance_invalid` | unknown stance |
| `tactic_actions_invalid` | `actions` is not a list |
| `tactic_too_many_actions` | more than 4 actions |
| `tactic_action_invalid` | action shape or extra action field is invalid |
| `tactic_move_unknown` | move is not allowlisted |
| `tactic_predicate_unknown` | predicate is not allowlisted |
| `tactic_predicate_invalid` | predicate value or shape is invalid |
| `tactic_emote_invalid` | emote identifier is invalid |
| `ruleset_unsupported` | ruleset version is not `battle-1` or `battle-2` |
| `type_unknown` | `battle-2` pet type is not one of the five |
| `type_unmapped` | `battle-2` species has no type mapping |
| `pet_invalid` | pet does not declare a species |
| `species_unknown` | species is not one of the three v1 species |
| `seed_invalid` | seed is not an integer or short string |

## Resolution

Each round runs in this order:

1. Decrement cooldowns for both pets.
2. Evaluate each card against the state at the start of the round and choose
   one move per pet.
3. If a chosen move is still on cooldown, substitute `basic_attack` and record
   `fallback_from` and `reason: "cooldown"` in the event.
4. Mark which pets chose `guard` for this round.
5. Order the actors by effective speed, descending. Equal speed is broken by
   a deterministic draw from the committed seed.
6. Apply actions in that order. Damage or healing is applied immediately.
   The round stops early if a pet reaches 0 HP.
7. Record each action as one replay event.

`opponent_guarding` sees the opponent's guard choice from the previous round.
`special_ready` is true when `glitch_pulse` is not on cooldown.

The match stops at 0 HP or after round 6, whichever comes first.

### Damage

```text
raw = max(1, move_power + 2 * attacker_attack - defender_guard)
raw += focus_spent * (2 + attacker_focus // 2)
damage = max(1, raw * 60 // 100)   # only when guard applies
```

Guard applies when the defender chose `guard` in the current round and the
attacking move does not pierce guard. `quick_strike` pierces guard, so it uses
`raw` directly. Guard still subtracts its stat value before the percentage.

All focused charges are spent by the next damaging move. `glitch_pulse` is a
normal damaging move for focus purposes.

### Tie-break after round 6

If both pets are alive:

1. Higher remaining HP percentage wins (cross-multiplied, no floats).
2. Higher remaining absolute HP wins.
3. Higher total damage dealt wins.
4. Higher effective speed wins.
5. A deterministic draw from the committed seed picks the winner.

`result` is `"ko"` when a pet reaches 0 HP, otherwise `"decision"`. A
simultaneous double KO would be `"ko"` with `winner: null`; sequential
resolution makes this unreachable in normal play.

## Replay

`Replay.to_dict()` is JSON-serializable:

```json
{
  "ruleset_version": "battle-1",
  "seed": 42,
  "replay_hash": "<64 hex characters>",
  "rounds": 5,
  "winner": "a",
  "result": "ko",
  "final_hp": {"a": 28, "b": 0},
  "events": [
    {
      "round": 1,
      "actor": "a",
      "move": "basic_attack",
      "hp_before": {"a": 100, "b": 100},
      "hp_after": {"a": 100, "b": 80},
      "status_delta": {
        "target": "b",
        "damage": 20,
        "raw_damage": 20,
        "guarded": false,
        "guard_reduced": false,
        "focus_spent": 0,
        "hp_remaining": 80
      },
      "result": "hit",
      "rng_counter": 0
    }
  ]
}
```

`actor` is `"a"` or `"b"`. `hp_before` and `hp_after` contain both sides'
HP at the moment the action is applied. `status_delta` is move-specific:
attacks include damage, guard/focus state, special/fallback details; guard,
focus, and heal include their own fields. `rng_counter` is the number of
seeded draws consumed before that event.

### Hash

`replay_hash` is the lowercase SHA-256 hex digest of the canonical JSON of the
`events` list:

```python
canonical = json.dumps(
    events,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=True,
    allow_nan=False,
)
digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

`Replay.verify_hash()` recomputes and compares the digest. The hash covers
events only, as frozen by `contracts-v1`; `ruleset_version` is a separate
field.

## Determinism guarantees

- The engine uses no wall clock, process RNG, network, database, environment,
  or mutable global state.
- Randomness is a SHA-256 counter stream derived from the committed seed and
  is used only for equal-speed initiative and the final tie-break.
- Inputs are not mutated. Tactic validation returns a fresh normalized card.
- The same inputs and seed produce byte-identical replays and hashes.
- `server/tests/test_combat_engine.py` checks this for 100 sampled seeds and
  against a checked-in golden fixture.

## Test command

```sh
python3 -m pytest -q server/tests/test_combat_engine.py
```

The tests and engine require only the Python 3 standard library plus pytest.
No real network, HTTP routes, database, ledger, wallet, reward entitlement, or
rating code is part of this slice.

## Type effectiveness (`battle-2`)

`battle-2` extends the same species stats, stances, moves, and round structure
with a five-type pentagon chart, STAB, and one passive per type. `battle-1`
inputs and golden replays are unchanged — type fields on pets are ignored under
`battle-1`. See [`TYPES.md`](./TYPES.md) for the chart, species mapping, balance
targets, and seeded flat damage variance (`status_delta.damage_variance`). Opt into types by passing `ruleset="battle-2"` (and matching
tactic `ruleset_version`).

