"""Tests for battle-2 type chart, passives, and battle-1 replay stability."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app.combat import (
    BATTLE_1_VERSION,
    BATTLE_2_VERSION,
    NVE,
    RULESET_VERSION,
    SE,
    SPECIES_TYPES,
    STAB,
    TYPE_CHART,
    TYPE_ORDER,
    TYPE_PASSIVES,
    TYPES,
    CombatError,
    effectiveness,
    resolve_match,
    validate_tactic_card,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "replays" / "battle-1_patchfox_vs_byteblob_seed42.json"
)


def pet(species, type_id=None):
    value = {"species": species}
    if type_id is not None:
        value["type"] = type_id
    return value


def card(ruleset, stance="balanced", move="basic_attack"):
    return {
        "ruleset_version": ruleset,
        "stance": stance,
        "actions": [{"when": {"always": True}, "move": move}],
    }


def test_five_types_form_balanced_pentagon():
    assert TYPE_ORDER == ("signal", "kernel", "payload", "firewall", "glitch")
    assert TYPES == set(TYPE_ORDER)
    assert set(TYPE_PASSIVES) == TYPES
    for i, atk in enumerate(TYPE_ORDER):
        se = nve = neu = 0
        for j, dfn in enumerate(TYPE_ORDER):
            mult = TYPE_CHART[atk][dfn]
            if mult == SE:
                se += 1
                assert (j - i) % 5 in (1, 2)
            elif mult == NVE:
                nve += 1
                assert (j - i) % 5 in (3, 4)
            else:
                neu += 1
                assert i == j
        assert (se, nve, neu) == (2, 2, 1)
        # Mirror: A SE vs B ⇒ B NVE vs A
        for dfn in TYPE_ORDER:
            forward = TYPE_CHART[atk][dfn]
            reverse = TYPE_CHART[dfn][atk]
            if forward == SE:
                assert reverse == NVE
            elif forward == NVE:
                assert reverse == SE


def test_species_type_mapping_covers_starters():
    assert SPECIES_TYPES["byteblob"] == "kernel"
    assert SPECIES_TYPES["patchfox"] == "payload"
    assert SPECIES_TYPES["nullgeist"] == "glitch"


def test_battle_1_golden_replay_unchanged():
    fixture = json.loads(FIXTURE.read_text())
    replay = resolve_match(
        fixture["ruleset"],
        fixture["pet_a"],
        fixture["pet_b"],
        fixture["tactics_a"],
        fixture["tactics_b"],
        fixture["seed"],
    )
    expected = fixture["expected"]
    assert replay.ruleset_version == BATTLE_1_VERSION == RULESET_VERSION
    assert replay.replay_hash == expected["replay_hash"]
    assert replay.winner == expected["winner"]
    assert replay.rounds == expected["rounds"]


def test_battle_1_ignores_type_override():
    a = resolve_match(
        BATTLE_1_VERSION,
        pet("byteblob", "signal"),
        pet("byteblob", "glitch"),
        None,
        None,
        7,
    )
    b = resolve_match(
        BATTLE_1_VERSION,
        pet("byteblob"),
        pet("byteblob"),
        None,
        None,
        7,
    )
    assert a.replay_hash == b.replay_hash
    assert a.ruleset_version == BATTLE_1_VERSION


def test_battle_2_applies_type_multiplier_and_stab():
    # Equal chassis; SE+STAB should out-damage NVE+STAB.
    se = resolve_match(
        BATTLE_2_VERSION,
        pet("byteblob", "signal"),
        pet("byteblob", "kernel"),
        card(BATTLE_2_VERSION),
        card(BATTLE_2_VERSION),
        99,
    )
    assert se.winner == "a"
    hit = next(e for e in se.events if e["move"] == "basic_attack" and e["actor"] == "a")
    assert hit["status_delta"]["move_type"] == "signal"
    assert hit["status_delta"]["type_multiplier"] == [SE[0], SE[1]]
    assert hit["status_delta"]["stab_multiplier"] == [STAB[0], STAB[1]]


def test_battle_2_defaults_type_from_species():
    replay = resolve_match(
        BATTLE_2_VERSION,
        pet("patchfox"),
        pet("byteblob"),
        card(BATTLE_2_VERSION),
        card(BATTLE_2_VERSION),
        3,
    )
    assert replay.ruleset_version == BATTLE_2_VERSION
    # patchfox=payload is SE vs byteblob=kernel? payload beats firewall+glitch, not kernel.
    # kernel beats payload (SE). So byteblob (kernel) should beat patchfox (payload).
    assert replay.winner == "b"


def test_battle_2_rejects_unknown_type():
    with pytest.raises(CombatError) as err:
        resolve_match(
            BATTLE_2_VERSION,
            pet("byteblob", "dragon"),
            pet("byteblob"),
            card(BATTLE_2_VERSION),
            card(BATTLE_2_VERSION),
            1,
        )
    assert err.value.code == "type_unknown"


def test_battle_2_tactic_ruleset_must_match():
    with pytest.raises(CombatError) as err:
        validate_tactic_card(card(BATTLE_1_VERSION), BATTLE_2_VERSION)
    assert err.value.code == "tactic_ruleset_mismatch"


def test_effectiveness_helper():
    assert effectiveness("signal", "kernel") == SE
    assert effectiveness("kernel", "signal") == NVE
    assert effectiveness("signal", "signal") == (1, 1)
    assert effectiveness(None, "signal") == (1, 1)


def test_battle_2_deterministic_across_seeds_sample():
    for seed in range(20):
        a = resolve_match(
            BATTLE_2_VERSION,
            pet("nullgeist"),
            pet("patchfox"),
            card(BATTLE_2_VERSION, "control"),
            card(BATTLE_2_VERSION, "aggressive"),
            seed,
        )
        b = resolve_match(
            BATTLE_2_VERSION,
            pet("nullgeist"),
            pet("patchfox"),
            card(BATTLE_2_VERSION, "control"),
            card(BATTLE_2_VERSION, "aggressive"),
            seed,
        )
        assert a.replay_hash == b.replay_hash
        assert a.to_dict() == b.to_dict()
