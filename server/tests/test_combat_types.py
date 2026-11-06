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
    DAMAGE_VARIANCE_FLAT,
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
    assert SPECIES_TYPES["cachebat"] == "signal"
    assert SPECIES_TYPES["firewyrm"] == "firewall"
    assert len(SPECIES_TYPES) == 10
    # two of each type
    from collections import Counter
    counts = Counter(SPECIES_TYPES.values())
    assert set(counts) == set(TYPES)
    assert all(v == 2 for v in counts.values())


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
    # Equal chassis; event records SE+STAB multipliers (winner may vary with variance).
    se = resolve_match(
        BATTLE_2_VERSION,
        pet("byteblob", "signal"),
        pet("byteblob", "kernel"),
        card(BATTLE_2_VERSION),
        card(BATTLE_2_VERSION),
        99,
    )
    hit = next(e for e in se.events if e["move"] == "basic_attack" and e["actor"] == "a")
    assert hit["status_delta"]["move_type"] == "signal"
    assert hit["status_delta"]["type_multiplier"] == [SE[0], SE[1]]
    assert hit["status_delta"]["stab_multiplier"] == [STAB[0], STAB[1]]
    assert "damage_variance" in hit["status_delta"]


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


def test_battle_2_damage_variance_is_seeded_and_bounded():
    from server.app.combat import DAMAGE_VARIANCE_FLAT

    card = {
        "ruleset_version": BATTLE_2_VERSION,
        "stance": "balanced",
        "actions": [{"when": {"always": True}, "move": "basic_attack"}],
    }
    a = resolve_match(
        BATTLE_2_VERSION,
        pet("byteblob", "signal"),
        pet("byteblob", "kernel"),
        card,
        card,
        12345,
    )
    b = resolve_match(
        BATTLE_2_VERSION,
        pet("byteblob", "signal"),
        pet("byteblob", "kernel"),
        card,
        card,
        12345,
    )
    assert a.replay_hash == b.replay_hash
    assert a.to_dict() == b.to_dict()
    variances = [
        e["status_delta"]["damage_variance"]
        for e in a.events
        if e["move"] == "basic_attack"
    ]
    assert variances
    assert all(-DAMAGE_VARIANCE_FLAT <= v <= DAMAGE_VARIANCE_FLAT for v in variances)
    # Different seed should usually diverge (almost always with variance).
    c = resolve_match(
        BATTLE_2_VERSION,
        pet("byteblob", "signal"),
        pet("byteblob", "kernel"),
        card,
        card,
        99999,
    )
    assert c.replay_hash != a.replay_hash


def test_battle_1_still_has_no_damage_variance_field():
    replay = resolve_match(
        BATTLE_1_VERSION,
        pet("byteblob"),
        pet("patchfox"),
        None,
        None,
        7,
    )
    for event in replay.events:
        if event["move"] in {"basic_attack", "quick_strike", "glitch_pulse"}:
            assert "damage_variance" not in event["status_delta"]


def test_type_balance_eval_meets_soft_counter_targets():
    import sys
    from pathlib import Path as P

    root = P(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from evals.type_balance import run

    report = run(seeds=80, base_seed=10_000)
    assert report["ok"], report["failures"]
    assert 0.60 <= report["se_matchup_mean"] <= 0.70
    assert 0.45 <= report["mirror_matchup_mean"] <= 0.55
    for rate in report["overall_win_rate"].values():
        assert 0.47 <= rate <= 0.53
