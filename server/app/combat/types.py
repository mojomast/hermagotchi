"""Hermagotchi type chart for ruleset battle-2.

Symmetric 5-cycle (RPS-5 / pentagon): each type is super-effective against the
next two clockwise and resisted by the previous two. Mirror of Rock-Paper-
Scissors-Lizard-Spock fairness: with odd n, each strategy beats (n-1)/2 others.
"""

from __future__ import annotations

# Clockwise order. Index i beats (i+1) % 5 and (i+2) % 5.
TYPE_ORDER = ("signal", "kernel", "payload", "firewall", "glitch")
TYPES = frozenset(TYPE_ORDER)

# Attacker -> defender -> multiplier as (numerator, denominator) for integer math.
# Sized for a 6-round / 100 HP format (milder than Pokémon main-series 2×/½).
# SE 5/4 + STAB 5/4 = 25/16 ≈ 1.56×; NVE 4/5 + STAB 5/4 = 1× (resisted STAB
# lands as neutral — coverage stays meaningful).
SE = (5, 4)
NVE = (4, 5)
NEUTRAL = (1, 1)
STAB = (5, 4)

TYPE_CHART: dict[str, dict[str, tuple[int, int]]] = {}
for i, atk in enumerate(TYPE_ORDER):
    row: dict[str, tuple[int, int]] = {}
    for j, dfn in enumerate(TYPE_ORDER):
        delta = (j - i) % 5
        if delta in (1, 2):
            row[dfn] = SE
        elif delta in (3, 4):
            row[dfn] = NVE
        else:
            row[dfn] = NEUTRAL
    TYPE_CHART[atk] = row


TYPE_PASSIVES = {
    "signal": {
        "id": "ping",
        "summary": "+1 effective speed (initiative).",
    },
    "kernel": {
        "id": "rootkit",
        "summary": "+1 focus stat (stronger spent focus bonus).",
    },
    "payload": {
        "id": "zero_day",
        "summary": "First damaging hit this match deals +1 raw damage.",
    },
    "firewall": {
        "id": "hardened",
        "summary": "First incoming hit this match takes -1 damage (min 1).",
    },
    "glitch": {
        "id": "undefined",
        "summary": "While HP ≤ 50%, +1 attack.",
    },
}


# Existing launch-003 species + planned art expansion to 10 (2 per type).
# Planned names are reserved for the art worker; do not invent assets here.
# Live launch-003 roster (10 species, 2 per type).
SPECIES_TYPES = {
    "cachebat": "signal",
    "daemowl": "signal",
    "byteblob": "kernel",
    "kernelcrab": "kernel",
    "patchfox": "payload",
    "shellsnail": "payload",
    "stacktoise": "firewall",
    "firewyrm": "firewall",
    "nullgeist": "glitch",
    "regexopus": "glitch",
}

# Kept for docs/back-compat; all launch-003 names now live in SPECIES_TYPES.
PLANNED_SPECIES_TYPES: dict[str, str] = {}

ALL_SPECIES_TYPES = {**SPECIES_TYPES, **PLANNED_SPECIES_TYPES}


TYPE_ATTACK_THEMES = {
    "signal": {
        "flavor": "Broadcast, ping, jam, interrupt — RF and messaging.",
        "example_moves": ("ping_burst", "carrier_wave", "noise_floor"),
        "ability": TYPE_PASSIVES["signal"],
    },
    "kernel": {
        "flavor": "Syscalls, privilege, panic — OS core and hardware control.",
        "example_moves": ("syscall_spike", "privilege_escalation", "kernel_panic"),
        "ability": TYPE_PASSIVES["kernel"],
    },
    "payload": {
        "flavor": "Inject, overflow, shell — offensive code delivery.",
        "example_moves": ("shellcode", "buffer_smash", "rop_chain"),
        "ability": TYPE_PASSIVES["payload"],
    },
    "firewall": {
        "flavor": "Block, quarantine, harden — perimeter and policy.",
        "example_moves": ("packet_drop", "quarantine", "tls_handshake"),
        "ability": TYPE_PASSIVES["firewall"],
    },
    "glitch": {
        "flavor": "Corrupt, desync, undefined — chaos and side effects.",
        "example_moves": ("segfault_pulse", "heap_spray", "undefined_behavior"),
        "ability": TYPE_PASSIVES["glitch"],
    },
}


# Attack moves inherit the attacker's type (STAB). No universal coverage special:
# a fixed glitch-typed special broke the pentagon (everyone punched signal/kernel).
# Per-type signature moves can land in a later ruleset.
MOVE_TYPE_OVERRIDE: dict[str, str] = {}


def effectiveness(move_type: str | None, defender_type: str) -> tuple[int, int]:
    if move_type is None or move_type not in TYPES or defender_type not in TYPES:
        return NEUTRAL
    return TYPE_CHART[move_type][defender_type]


def apply_multiplier(damage: int, num: int, den: int) -> int:
    if damage <= 0:
        return damage
    return max(1, damage * num // den)


def resolve_move_type(move: str, attacker_type: str) -> str | None:
    if move in MOVE_TYPE_OVERRIDE:
        return MOVE_TYPE_OVERRIDE[move]
    from .ruleset import MOVES

    kind = MOVES.get(move, {}).get("kind")
    if kind == "attack":
        return attacker_type
    return None
