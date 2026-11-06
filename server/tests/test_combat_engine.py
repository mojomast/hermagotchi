import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app.combat import (
    BASE_HP,
    MAX_ROUNDS,
    MOVES,
    NEUTRAL_TACTIC,
    RULESET_VERSION,
    SPECIES_STATS,
    CombatError,
    Replay,
    TacticValidationError,
    canonical_json,
    resolve_match,
    validate_tactic_card,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "replays"


def pet(species, pet_id=None):
    return {"pet_id": pet_id or f"pet-{species}", "species": species}


def card(stance, actions, emote_id=None):
    value = {"ruleset_version": RULESET_VERSION, "stance": stance, "actions": actions}
    if emote_id is not None:
        value["emote_id"] = emote_id
    return value


ALWAYS_ATTACK = card("balanced", [{"when": {"always": True}, "move": "basic_attack"}])
AGGRESSIVE_ATTACK = card(
    "aggressive", [{"when": {"always": True}, "move": "basic_attack"}]
)
ALWAYS_GUARD = card("balanced", [{"when": {"always": True}, "move": "guard"}])
CONTRACT_EXAMPLE = {
    "ruleset_version": "battle-1",
    "stance": "control",
    "actions": [
        {"when": {"self_hp_lte_pct": 30}, "move": "guard"},
        {"when": {"special_ready": True}, "move": "glitch_pulse"},
        {"when": {"opponent_guarding": True}, "move": "focus"},
        {"when": {"always": True}, "move": "basic_attack"},
    ],
    "emote_id": "emote.sparkle",
}


def test_ruleset_constants_are_frozen():
    assert RULESET_VERSION == "battle-1"
    assert BASE_HP == 100
    assert MAX_ROUNDS == 6
    assert set(SPECIES_STATS) == {"byteblob", "patchfox", "nullgeist"}
    for stats in SPECIES_STATS.values():
        assert stats["max_hp"] == BASE_HP
        assert stats["attack"] + stats["guard"] + stats["speed"] + stats["focus"] == 20
    for move in ("basic_attack", "guard", "focus", "glitch_pulse"):
        assert move in MOVES
    assert 5 <= len(MOVES) <= 7


def test_validate_accepts_contract_example():
    validated = validate_tactic_card(CONTRACT_EXAMPLE)
    assert validated["ruleset_version"] == "battle-1"
    assert validated["stance"] == "control"
    assert validated["emote_id"] == "emote.sparkle"
    assert len(validated["actions"]) == 4
    assert validated == CONTRACT_EXAMPLE


@pytest.mark.parametrize(
    "bad_card,code",
    [
        (
            {"ruleset_version": "battle-9", "stance": "balanced", "actions": []},
            "tactic_ruleset_mismatch",
        ),
        (
            {"ruleset_version": "battle-1", "stance": "reckless", "actions": []},
            "tactic_stance_invalid",
        ),
        (
            {
                "ruleset_version": "battle-1",
                "stance": "balanced",
                "actions": [{"when": {"always": True}, "move": "basic_attack"}] * 5,
            },
            "tactic_too_many_actions",
        ),
        (
            {
                "ruleset_version": "battle-1",
                "stance": "balanced",
                "actions": [{"when": {"always": True}, "move": "hyper_beam"}],
            },
            "tactic_move_unknown",
        ),
        (
            {
                "ruleset_version": "battle-1",
                "stance": "balanced",
                "actions": [{"when": {"magic": True}, "move": "basic_attack"}],
            },
            "tactic_predicate_unknown",
        ),
        (
            {
                "ruleset_version": "battle-1",
                "stance": "balanced",
                "actions": [{"when": {"self_hp_lte_pct": "low"}, "move": "guard"}],
            },
            "tactic_predicate_invalid",
        ),
        (
            {
                "ruleset_version": "battle-1",
                "stance": "balanced",
                "actions": [
                    {"when": {"always": True}, "move": "basic_attack", "script": "x"}
                ],
            },
            "tactic_action_invalid",
        ),
        (
            {"ruleset_version": "battle-1", "stance": "balanced", "actions": {}},
            "tactic_actions_invalid",
        ),
        (
            {
                "ruleset_version": "battle-1",
                "stance": "balanced",
                "actions": [],
                "emote_id": "emote.<script>",
            },
            "tactic_emote_invalid",
        ),
        (
            {
                "ruleset_version": "battle-1",
                "stance": "balanced",
                "actions": [],
                "payload": "ignored",
            },
            "tactic_field_unknown",
        ),
    ],
)
def test_invalid_tactic_cards_rejected_with_codes(bad_card, code):
    with pytest.raises(TacticValidationError) as excinfo:
        validate_tactic_card(bad_card)
    assert excinfo.value.code == code


def test_invalid_tactic_rejected_by_engine():
    bad = card("balanced", [{"when": {"always": True}, "move": "hyper_beam"}])
    with pytest.raises(TacticValidationError) as excinfo:
        resolve_match(RULESET_VERSION, pet("byteblob"), pet("patchfox"), bad, None, 7)
    assert excinfo.value.code == "tactic_move_unknown"


def test_missing_cards_use_neutral_default():
    replay_none = resolve_match(
        RULESET_VERSION, pet("byteblob"), pet("patchfox"), None, None, 11
    )
    replay_default = resolve_match(
        RULESET_VERSION,
        pet("byteblob"),
        pet("patchfox"),
        NEUTRAL_TACTIC,
        NEUTRAL_TACTIC,
        11,
    )
    assert replay_none.to_dict() == replay_default.to_dict()
    assert replay_none.replay_hash == replay_default.replay_hash


def test_damage_formula_and_guard_reduction():
    attacker = pet("patchfox")
    defender = pet("byteblob")
    replay = resolve_match(
        RULESET_VERSION, attacker, defender, AGGRESSIVE_ATTACK, ALWAYS_GUARD, 3
    )
    first = replay.events[0]
    raw = 8 + 2 * (7 + 2) - 6
    reduced = max(1, raw * 60 // 100)
    assert first["actor"] == "a"
    assert first["move"] == "basic_attack"
    assert first["status_delta"]["damage"] == reduced
    assert first["status_delta"]["guarded"] is True
    assert first["hp_after"]["b"] == BASE_HP - reduced


def test_quick_strike_pierces_guard():
    quick = card("aggressive", [{"when": {"always": True}, "move": "quick_strike"}])
    replay = resolve_match(
        RULESET_VERSION, pet("patchfox"), pet("byteblob"), quick, ALWAYS_GUARD, 5
    )
    first = replay.events[0]
    raw = 5 + 2 * (7 + 2) - 6
    assert first["move"] == "quick_strike"
    assert first["status_delta"]["damage"] == raw
    assert first["status_delta"]["guarded"] is True


def test_aggressive_stance_changes_damage():
    balanced = resolve_match(
        RULESET_VERSION, pet("patchfox"), pet("byteblob"), ALWAYS_ATTACK, ALWAYS_ATTACK, 9
    )
    aggressive = resolve_match(
        RULESET_VERSION,
        pet("patchfox"),
        pet("byteblob"),
        AGGRESSIVE_ATTACK,
        ALWAYS_ATTACK,
        9,
    )
    assert balanced.events[0]["status_delta"]["damage"] == 16
    assert aggressive.events[0]["status_delta"]["damage"] == 20


def test_cooldown_falls_back_to_basic_attack():
    glitch = card("balanced", [{"when": {"always": True}, "move": "glitch_pulse"}])
    replay = resolve_match(
        RULESET_VERSION, pet("nullgeist"), pet("byteblob"), glitch, ALWAYS_GUARD, 13
    )
    assert replay.events[0]["move"] == "glitch_pulse"
    second_round = [event for event in replay.events if event["round"] == 2]
    assert second_round
    assert second_round[0]["move"] == "basic_attack"
    assert second_round[0]["status_delta"]["fallback_from"] == "glitch_pulse"
    assert second_round[0]["status_delta"]["reason"] == "cooldown"


def test_special_ready_and_focus_charges():
    tact = card(
        "control",
        [
            {"when": {"special_ready": True}, "move": "glitch_pulse"},
            {"when": {"always": True}, "move": "focus"},
        ],
    )
    replay = resolve_match(
        RULESET_VERSION, pet("nullgeist"), pet("byteblob"), tact, ALWAYS_GUARD, 17
    )
    moves = [(event["round"], event["actor"], event["move"]) for event in replay.events]
    assert (1, "a", "glitch_pulse") in moves
    assert (2, "a", "focus") in moves
    assert (3, "a", "focus") in moves
    glitches = [
        event
        for event in replay.events
        if event["actor"] == "a" and event["move"] == "glitch_pulse"
    ]
    assert len(glitches) >= 2
    assert glitches[1]["status_delta"]["focus_spent"] == 2


def test_ko_stops_match_early():
    replay = resolve_match(
        RULESET_VERSION,
        pet("patchfox", "a"),
        pet("byteblob", "b"),
        AGGRESSIVE_ATTACK,
        ALWAYS_ATTACK,
        2,
    )
    assert replay.result == "ko"
    assert replay.winner == "a"
    assert replay.rounds < MAX_ROUNDS
    assert replay.final_hp["b"] == 0
    assert replay.events[-1]["result"] == "ko"


def test_six_round_cap_without_ko():
    replay = resolve_match(
        RULESET_VERSION,
        pet("byteblob"),
        pet("byteblob"),
        ALWAYS_GUARD,
        ALWAYS_GUARD,
        23,
    )
    assert replay.rounds == MAX_ROUNDS
    assert replay.result in {"decision", "draw"}
    assert replay.final_hp == {"a": BASE_HP, "b": BASE_HP}
    assert max(event["round"] for event in replay.events) == MAX_ROUNDS


def test_tie_break_uses_remaining_hp():
    replay = resolve_match(
        RULESET_VERSION,
        pet("byteblob"),
        pet("patchfox"),
        ALWAYS_GUARD,
        AGGRESSIVE_ATTACK,
        29,
    )
    assert replay.result == "decision"
    assert replay.rounds == MAX_ROUNDS
    assert replay.winner == "b"
    assert replay.final_hp["b"] > replay.final_hp["a"]


def test_replay_hash_is_sha256_of_canonical_events():
    replay = resolve_match(
        RULESET_VERSION,
        pet("patchfox"),
        pet("byteblob"),
        AGGRESSIVE_ATTACK,
        ALWAYS_ATTACK,
        31,
    )
    expected = hashlib.sha256(canonical_json(replay.events).encode("utf-8")).hexdigest()
    assert replay.replay_hash == expected
    assert re.fullmatch(r"[0-9a-f]{64}", replay.replay_hash)
    assert replay.verify_hash() is True


def test_fixed_seed_replay_is_byte_identical():
    first = resolve_match(
        RULESET_VERSION,
        pet("patchfox"),
        pet("byteblob"),
        AGGRESSIVE_ATTACK,
        ALWAYS_ATTACK,
        42,
    )
    second = resolve_match(
        RULESET_VERSION,
        pet("patchfox"),
        pet("byteblob"),
        AGGRESSIVE_ATTACK,
        ALWAYS_ATTACK,
        42,
    )
    assert isinstance(first, Replay)
    assert first.to_dict() == second.to_dict()
    assert first.replay_hash == second.replay_hash
    assert json.dumps(first.to_dict(), sort_keys=True)


def test_golden_replay_fixture():
    fixture_path = FIXTURE_DIR / "battle-1_patchfox_vs_byteblob_seed42.json"
    fixture = json.loads(fixture_path.read_text())
    replay = resolve_match(
        fixture["ruleset"],
        fixture["pet_a"],
        fixture["pet_b"],
        fixture["tactics_a"],
        fixture["tactics_b"],
        fixture["seed"],
    )
    assert replay.to_dict() == fixture["expected"]


def test_same_inputs_same_hash_across_100_sampled_seeds():
    for seed in range(100):
        first = resolve_match(
            RULESET_VERSION,
            pet("nullgeist"),
            pet("byteblob"),
            CONTRACT_EXAMPLE,
            ALWAYS_GUARD,
            seed,
        )
        second = resolve_match(
            RULESET_VERSION,
            pet("nullgeist"),
            pet("byteblob"),
            CONTRACT_EXAMPLE,
            ALWAYS_GUARD,
            seed,
        )
        assert first.replay_hash == second.replay_hash
        assert first.to_dict() == second.to_dict()
        assert first.verify_hash()


def test_inputs_are_not_mutated():
    tactics_a = copy.deepcopy(CONTRACT_EXAMPLE)
    tactics_b = copy.deepcopy(ALWAYS_GUARD)
    pet_a = pet("nullgeist")
    pet_b = pet("byteblob")
    expected = (copy.deepcopy(tactics_a), copy.deepcopy(tactics_b), dict(pet_a), dict(pet_b))
    resolve_match(RULESET_VERSION, pet_a, pet_b, tactics_a, tactics_b, 37)
    assert (tactics_a, tactics_b, pet_a, pet_b) == expected


def test_unknown_species_and_ruleset_rejected():
    with pytest.raises(CombatError) as species_error:
        resolve_match(
            RULESET_VERSION, pet("dragon"), pet("byteblob"), None, None, 1
        )
    assert species_error.value.code == "species_unknown"

    with pytest.raises(CombatError) as ruleset_error:
        resolve_match("battle-99", pet("byteblob"), pet("byteblob"), None, None, 1)
    assert ruleset_error.value.code == "ruleset_unsupported"


@pytest.mark.parametrize("move", sorted(MOVES))
def test_every_move_is_allowlisted(move):
    validated = validate_tactic_card(
        card("balanced", [{"when": {"always": True}, "move": move}])
    )
    assert validated["actions"][0]["move"] == move


def test_recover_heals_without_exceeding_max_hp():
    tact = card(
        "defensive",
        [
            {"when": {"self_hp_lte_pct": 90}, "move": "recover"},
            {"when": {"always": True}, "move": "guard"},
        ],
    )
    replay = resolve_match(
        RULESET_VERSION,
        pet("byteblob"),
        pet("patchfox"),
        tact,
        AGGRESSIVE_ATTACK,
        41,
    )
    heals = [event for event in replay.events if event["move"] == "recover"]
    assert heals
    assert all(event["status_delta"]["healed"] > 0 for event in heals)
    assert all(event["hp_after"]["a"] <= BASE_HP for event in replay.events)
