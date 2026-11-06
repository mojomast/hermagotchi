from dataclasses import dataclass

RULESET_VERSION = "battle-1"
BATTLE_1_VERSION = "battle-1"
BATTLE_2_VERSION = "battle-2"
SUPPORTED_RULESETS = frozenset({BATTLE_1_VERSION, BATTLE_2_VERSION})

BASE_HP = 100
MAX_ROUNDS = 6
STAT_BUDGET = 20
GUARD_REDUCTION_PCT = 40
FOCUS_MAX_CHARGES = 2
FOCUS_BONUS_BASE = 2
HEAL_POWER = 10

SPECIES_STATS = {
    "byteblob": {
        "max_hp": BASE_HP,
        "attack": 6,
        "guard": 6,
        "speed": 4,
        "focus": 4,
    },
    "patchfox": {
        "max_hp": BASE_HP,
        "attack": 7,
        "guard": 3,
        "speed": 7,
        "focus": 3,
    },
    "nullgeist": {
        "max_hp": BASE_HP,
        "attack": 5,
        "guard": 4,
        "speed": 5,
        "focus": 6,
    },
}

STANCES = {
    "aggressive": {"attack": 2, "guard": -1, "speed": 1},
    "balanced": {"attack": 0, "guard": 0, "speed": 0},
    "defensive": {"attack": -1, "guard": 3, "speed": -1},
    "control": {"attack": -1, "guard": 1, "speed": 2},
}

MOVES = {
    "basic_attack": {
        "kind": "attack",
        "power": 8,
        "cooldown": 0,
        "pierce_guard": False,
    },
    "quick_strike": {
        "kind": "attack",
        "power": 5,
        "cooldown": 1,
        "pierce_guard": True,
    },
    "guard": {
        "kind": "guard",
        "cooldown": 0,
    },
    "focus": {
        "kind": "focus",
        "cooldown": 0,
    },
    "glitch_pulse": {
        "kind": "attack",
        "power": 14,
        "cooldown": 2,
        "pierce_guard": False,
        "special": True,
    },
    "recover": {
        "kind": "heal",
        "cooldown": 3,
        "heal": HEAL_POWER,
    },
}

NEUTRAL_TACTIC = {
    "ruleset_version": RULESET_VERSION,
    "stance": "balanced",
    "actions": [{"when": {"always": True}, "move": "basic_attack"}],
}


def neutral_tactic_for(version: str) -> dict:
    tactic = {
        "ruleset_version": version,
        "stance": "balanced",
        "actions": [{"when": {"always": True}, "move": "basic_attack"}],
    }
    return tactic


ALLOWED_STANCES = frozenset(STANCES)
ALLOWED_MOVES = frozenset(MOVES)
ALLOWED_PREDICATES = frozenset(
    {"self_hp_lte_pct", "opponent_guarding", "special_ready", "always"}
)
ALLOWED_TACTIC_FIELDS = frozenset(
    {"ruleset_version", "stance", "actions", "emote_id"}
)


@dataclass(frozen=True)
class Ruleset:
    version: str = RULESET_VERSION
    max_rounds: int = MAX_ROUNDS
    base_hp: int = BASE_HP
    guard_reduction_pct: int = GUARD_REDUCTION_PCT
    stat_budget: int = STAT_BUDGET


BATTLE_1 = Ruleset(version=BATTLE_1_VERSION)
BATTLE_2 = Ruleset(version=BATTLE_2_VERSION)
RULESET = BATTLE_1
