#!/usr/bin/env python3
"""Seeded type-balance simulation for Hermagotchi battle-2.

Holds species/stats equal (byteblob body) and forces types so the chart +
passives are isolated from species asymmetry. Uses the real combat engine.

Under identical tactic cards the engine is deterministic, so a super-effective
matchup is a near-hard counter (A-win ≈ 100%). Balance is judged by:
  - each type's overall win rate ≈ 50% (no dominant type across the meta)
  - SE directionality (SE attacker wins the pairwise)
  - mirrors near 50%

Usage:
  python3 evals/type_balance.py
  python3 evals/type_balance.py --seeds 200 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app.combat import (  # noqa: E402
    BATTLE_2_VERSION,
    TYPE_CHART,
    TYPE_ORDER,
    resolve_match,
)

OVERALL_LO = 0.47
OVERALL_HI = 0.53
SE_DIR_LO = 0.90  # SE attacker should win the pairwise under equal tactics
MIRROR_LO = 0.45
MIRROR_HI = 0.55


def _card(stance: str = "balanced") -> dict:
    return {
        "ruleset_version": BATTLE_2_VERSION,
        "stance": stance,
        "actions": [
            {"when": {"special_ready": True}, "move": "glitch_pulse"},
            {"when": {"always": True}, "move": "basic_attack"},
        ],
    }


def _pet(type_id: str) -> dict:
    return {"species": "byteblob", "type": type_id}


def _is_se(attacker: str, defender: str) -> bool:
    num, den = TYPE_CHART[attacker][defender]
    return num * den > den * den  # num/den > 1 without floats: num > den


def run(seeds: int, base_seed: int = 10_000) -> dict:
    stances = ("balanced", "aggressive", "defensive", "control")
    wins = defaultdict(int)
    games = defaultdict(int)
    matchup = defaultdict(lambda: {"a_wins": 0, "games": 0})

    for i in range(seeds):
        seed = base_seed + i
        stance_a = stances[i % len(stances)]
        stance_b = stances[(i // len(stances)) % len(stances)]
        for atype in TYPE_ORDER:
            for btype in TYPE_ORDER:
                replay = resolve_match(
                    BATTLE_2_VERSION,
                    _pet(atype),
                    _pet(btype),
                    _card(stance_a),
                    _card(stance_b),
                    seed,
                )
                key = f"{atype}>{btype}"
                matchup[key]["games"] += 1
                games[atype] += 1
                games[btype] += 1
                if replay.winner == "a":
                    wins[atype] += 1
                    matchup[key]["a_wins"] += 1
                elif replay.winner == "b":
                    wins[btype] += 1

    overall = {
        t: (wins[t] / games[t] if games[t] else 0.0) for t in TYPE_ORDER
    }
    matchup_rates = {
        k: (v["a_wins"] / v["games"] if v["games"] else 0.0)
        for k, v in sorted(matchup.items())
    }

    se_rates = []
    mirror_rates = []
    for atype in TYPE_ORDER:
        for btype in TYPE_ORDER:
            rate = matchup_rates[f"{atype}>{btype}"]
            if atype == btype:
                mirror_rates.append(rate)
            elif _is_se(atype, btype):
                se_rates.append(rate)

    report = {
        "ruleset": BATTLE_2_VERSION,
        "seeds": seeds,
        "battles": seeds * len(TYPE_ORDER) * len(TYPE_ORDER),
        "overall_win_rate": overall,
        "matchup_a_win_rate": matchup_rates,
        "se_matchup_mean": sum(se_rates) / len(se_rates) if se_rates else 0.0,
        "mirror_matchup_mean": (
            sum(mirror_rates) / len(mirror_rates) if mirror_rates else 0.0
        ),
        "targets": {
            "overall": [OVERALL_LO, OVERALL_HI],
            "se_direction": [SE_DIR_LO, 1.0],
            "mirror": [MIRROR_LO, MIRROR_HI],
        },
    }

    failures = []
    for t, rate in overall.items():
        if not (OVERALL_LO <= rate <= OVERALL_HI):
            failures.append(
                f"overall[{t}]={rate:.4f} outside {OVERALL_LO}-{OVERALL_HI}"
            )
    if report["se_matchup_mean"] < SE_DIR_LO:
        failures.append(
            f"se_mean={report['se_matchup_mean']:.4f} below {SE_DIR_LO} "
            "(SE attacker should win pairwise under equal tactics)"
        )
    if not (MIRROR_LO <= report["mirror_matchup_mean"] <= MIRROR_HI):
        failures.append(
            f"mirror_mean={report['mirror_matchup_mean']:.4f} "
            f"outside {MIRROR_LO}-{MIRROR_HI}"
        )
    report["ok"] = not failures
    report["failures"] = failures
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=80)
    parser.add_argument("--base-seed", type=int, default=10_000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run(args.seeds, args.base_seed)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"battle-2 type balance — {report['battles']} battles "
            f"({report['seeds']} seeds × 5×5)"
        )
        print("overall win rates:")
        for t in TYPE_ORDER:
            print(f"  {t:10s}  {report['overall_win_rate'][t]*100:5.1f}%")
        print(
            f"SE matchup mean A-win:     {report['se_matchup_mean']*100:5.1f}%"
        )
        print(
            f"mirror matchup mean A-win: {report['mirror_matchup_mean']*100:5.1f}%"
        )
        print("matchup grid (A win %):")
        header = "          " + "".join(f"{t:>10s}" for t in TYPE_ORDER)
        print(header)
        for atype in TYPE_ORDER:
            row = f"{atype:10s}"
            for btype in TYPE_ORDER:
                rate = report["matchup_a_win_rate"][f"{atype}>{btype}"]
                row += f"{rate*100:9.1f}%"
            print(row)
        if report["ok"]:
            print("PASS: within targets")
        else:
            print("FAIL:")
            for f in report["failures"]:
                print(f"  - {f}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
