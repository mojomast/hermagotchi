import copy
import hashlib
import json
from dataclasses import dataclass, field

from .ruleset import (
    BATTLE_2_VERSION,
    FOCUS_BONUS_BASE,
    FOCUS_MAX_CHARGES,
    GUARD_REDUCTION_PCT,
    MAX_ROUNDS,
    MOVES,
    SPECIES_STATS,
    STANCES,
)
from .types import (
    DAMAGE_VARIANCE_FLAT,
    STAB,
    apply_multiplier,
    effectiveness,
    resolve_move_type,
)
from .validation import (
    CombatError,
    normalize_pet,
    normalize_ruleset,
    validate_tactic_card,
)


def canonical_json(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def compute_replay_hash(events):
    payload = canonical_json(list(events)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class Replay:
    ruleset_version: str
    seed: object
    events: list
    rounds: int
    winner: object
    result: str
    final_hp: dict
    replay_hash: str

    def to_dict(self):
        return {
            "ruleset_version": self.ruleset_version,
            "seed": self.seed,
            "replay_hash": self.replay_hash,
            "rounds": self.rounds,
            "winner": self.winner,
            "result": self.result,
            "final_hp": dict(self.final_hp),
            "events": copy.deepcopy(self.events),
        }

    def as_dict(self):
        return self.to_dict()

    def verify_hash(self):
        return compute_replay_hash(self.events) == self.replay_hash

    def __getitem__(self, key):
        return self.to_dict()[key]

    def get(self, key, default=None):
        return self.to_dict().get(key, default)


@dataclass
class _Fighter:
    side: str
    species: str
    pet_type: object
    max_hp: int
    attack: int
    guard: int
    speed: int
    focus: int
    hp: int
    focus_charge: int = 0
    guarding: bool = False
    round_guarding: bool = False
    cooldowns: dict = field(default_factory=dict)
    damage_dealt: int = 0
    # battle-2 passive state
    payload_first_hit_pending: bool = False
    firewall_first_hit_pending: bool = False
    base_attack: int = 0


class _SeededRng:
    def __init__(self, seed):
        self.material = canonical_json(seed)
        self.counter = 0

    def below(self, bound):
        digest = hashlib.sha256(
            f"{self.material}:{self.counter}".encode("utf-8")
        ).digest()
        self.counter += 1
        return int.from_bytes(digest[:8], "big") % bound


def _normalize_seed(seed):
    if isinstance(seed, bool):
        raise CombatError("seed_invalid", "seed must be an integer or string")
    if isinstance(seed, int):
        return seed
    if isinstance(seed, str) and 0 < len(seed) <= 128:
        return seed
    raise CombatError("seed_invalid", "seed must be an integer or string")


def _make_fighter(side, species, stance, pet_type, ruleset_version):
    stats = SPECIES_STATS[species]
    modifiers = STANCES[stance]
    attack = max(1, stats["attack"] + modifiers["attack"])
    guard = max(0, stats["guard"] + modifiers["guard"])
    speed = max(0, stats["speed"] + modifiers["speed"])
    focus = stats["focus"]

    payload_pending = False
    firewall_pending = False
    if ruleset_version == BATTLE_2_VERSION and pet_type is not None:
        if pet_type == "signal":
            speed += 1
        elif pet_type == "kernel":
            focus += 1
        elif pet_type == "payload":
            payload_pending = True
        elif pet_type == "firewall":
            firewall_pending = True
        # glitch passive is dynamic (undefined) — applied at damage time

    return _Fighter(
        side=side,
        species=species,
        pet_type=pet_type,
        max_hp=stats["max_hp"],
        attack=attack,
        guard=guard,
        speed=speed,
        focus=focus,
        hp=stats["max_hp"],
        payload_first_hit_pending=payload_pending,
        firewall_first_hit_pending=firewall_pending,
        base_attack=attack,
    )


def _effective_attack(fighter, ruleset_version):
    attack = fighter.attack
    if (
        ruleset_version == BATTLE_2_VERSION
        and fighter.pet_type == "glitch"
        and fighter.hp * 10 <= 3 * fighter.max_hp
    ):
        attack = fighter.base_attack + 1
    return attack


def _predicate_matches(when, fighter, opponent):
    key, value = next(iter(when.items()))
    if key == "always":
        return value
    if key == "self_hp_lte_pct":
        return fighter.hp * 100 <= value * fighter.max_hp
    if key == "opponent_guarding":
        return opponent.guarding is value
    if key == "special_ready":
        ready = fighter.cooldowns.get("glitch_pulse", 0) == 0
        return ready is value
    return False


def _select_move(fighter, opponent, tactic):
    for action in tactic["actions"]:
        if _predicate_matches(action["when"], fighter, opponent):
            return action["move"]
    return "basic_attack"


def _tick_cooldowns(fighter):
    expired = []
    for move, remaining in fighter.cooldowns.items():
        if remaining <= 1:
            expired.append(move)
        else:
            fighter.cooldowns[move] = remaining - 1
    for move in expired:
        del fighter.cooldowns[move]


def _set_cooldown(fighter, move):
    cooldown = MOVES[move].get("cooldown", 0)
    if cooldown:
        fighter.cooldowns[move] = cooldown + 1


def _available(fighter, move):
    return fighter.cooldowns.get(move, 0) == 0


def _focus_bonus(fighter):
    return FOCUS_BONUS_BASE + fighter.focus // 2


def _snapshot_hp(fighter_a, fighter_b):
    return {"a": fighter_a.hp, "b": fighter_b.hp}


def _apply_move(round_number, actor, defender, move, fallback, rng, ruleset_version):
    move_def = MOVES[move]
    hp_before = _snapshot_hp(
        actor if actor.side == "a" else defender,
        defender if actor.side == "a" else actor,
    )
    status = {}
    kind = move_def["kind"]

    if kind == "attack":
        focus_spent = actor.focus_charge
        actor.focus_charge = 0
        attack_stat = _effective_attack(actor, ruleset_version)
        raw = move_def["power"] + 2 * attack_stat - defender.guard
        if focus_spent:
            raw += focus_spent * _focus_bonus(actor)
        if (
            ruleset_version == BATTLE_2_VERSION
            and actor.payload_first_hit_pending
        ):
            raw += 1
            actor.payload_first_hit_pending = False
            status_payload = True
        else:
            status_payload = False
        raw = max(1, raw)
        guarded = defender.round_guarding
        guard_reduced = guarded and not move_def.get("pierce_guard", False)
        damage = raw
        if guard_reduced:
            damage = max(1, raw * (100 - GUARD_REDUCTION_PCT) // 100)

        type_mult = (1, 1)
        stab_mult = (1, 1)
        move_type = None
        if ruleset_version == BATTLE_2_VERSION and actor.pet_type is not None:
            move_type = resolve_move_type(move, actor.pet_type)
            if move_type is not None and defender.pet_type is not None:
                type_mult = effectiveness(move_type, defender.pet_type)
                damage = apply_multiplier(damage, type_mult[0], type_mult[1])
            if move_type is not None and move_type == actor.pet_type:
                stab_mult = STAB
                damage = apply_multiplier(damage, stab_mult[0], stab_mult[1])

        if (
            ruleset_version == BATTLE_2_VERSION
            and defender.firewall_first_hit_pending
        ):
            damage = max(1, damage - 1)
            defender.firewall_first_hit_pending = False
            status_firewall = True
        else:
            status_firewall = False

        variance_delta = 0
        if ruleset_version == BATTLE_2_VERSION:
            # Deterministic: next draw from the committed seed stream.
            # Inclusive flat band: [-DAMAGE_VARIANCE_FLAT, +DAMAGE_VARIANCE_FLAT].
            variance_delta = (
                rng.below(2 * DAMAGE_VARIANCE_FLAT + 1) - DAMAGE_VARIANCE_FLAT
            )
            damage = max(1, damage + variance_delta)

        defender.hp = max(0, defender.hp - damage)
        actor.damage_dealt += damage
        status = {
            "target": defender.side,
            "damage": damage,
            "raw_damage": raw,
            "guarded": guarded,
            "guard_reduced": guard_reduced,
            "focus_spent": focus_spent,
            "hp_remaining": defender.hp,
        }
        if ruleset_version == BATTLE_2_VERSION:
            status["move_type"] = move_type
            status["type_multiplier"] = [type_mult[0], type_mult[1]]
            status["stab_multiplier"] = [stab_mult[0], stab_mult[1]]
            status["damage_variance"] = variance_delta
            if status_payload:
                status["passive"] = "zero_day"
            if status_firewall:
                status["defender_passive"] = "hardened"
        result = "ko" if defender.hp == 0 else "hit"
    elif kind == "guard":
        status = {"guarding": True}
        result = "guard"
    elif kind == "focus":
        before = actor.focus_charge
        actor.focus_charge = min(FOCUS_MAX_CHARGES, before + 1)
        status = {
            "focus_charge": actor.focus_charge,
            "focus_gained": actor.focus_charge - before,
        }
        result = "focus"
    elif kind == "heal":
        healed = min(move_def["heal"], actor.max_hp - actor.hp)
        actor.hp += healed
        status = {"healed": healed, "hp_remaining": actor.hp}
        result = "heal"
    else:
        raise CombatError("move_invalid", f"unsupported move kind: {kind!r}")

    if fallback is not None:
        status["fallback_from"] = fallback
        status["reason"] = "cooldown"

    _set_cooldown(actor, move)
    hp_after = _snapshot_hp(
        actor if actor.side == "a" else defender,
        defender if actor.side == "a" else actor,
    )
    return {
        "round": round_number,
        "actor": actor.side,
        "move": move,
        "hp_before": hp_before,
        "hp_after": hp_after,
        "status_delta": status,
        "result": result,
        "rng_counter": rng.counter,
    }


def _initiative(fighter_a, fighter_b, rng):
    if fighter_a.speed > fighter_b.speed:
        return fighter_a, fighter_b
    if fighter_b.speed > fighter_a.speed:
        return fighter_b, fighter_a
    if rng.below(2) == 0:
        return fighter_a, fighter_b
    return fighter_b, fighter_a


def _decide_winner(fighter_a, fighter_b, rng):
    left = fighter_a.hp * fighter_b.max_hp
    right = fighter_b.hp * fighter_a.max_hp
    if left != right:
        return "a" if left > right else "b"
    if fighter_a.hp != fighter_b.hp:
        return "a" if fighter_a.hp > fighter_b.hp else "b"
    if fighter_a.damage_dealt != fighter_b.damage_dealt:
        return "a" if fighter_a.damage_dealt > fighter_b.damage_dealt else "b"
    if fighter_a.speed != fighter_b.speed:
        return "a" if fighter_a.speed > fighter_b.speed else "b"
    return "a" if rng.below(2) == 0 else "b"


def resolve_match(ruleset, pet_a, pet_b, tactics_a, tactics_b, seed):
    version = normalize_ruleset(ruleset)
    identity_a = normalize_pet(pet_a, version)
    identity_b = normalize_pet(pet_b, version)
    tactic_a = validate_tactic_card(tactics_a, version)
    tactic_b = validate_tactic_card(tactics_b, version)
    normalized_seed = _normalize_seed(seed)
    rng = _SeededRng(normalized_seed)

    fighter_a = _make_fighter(
        "a",
        identity_a["species"],
        tactic_a["stance"],
        identity_a["type"],
        version,
    )
    fighter_b = _make_fighter(
        "b",
        identity_b["species"],
        tactic_b["stance"],
        identity_b["type"],
        version,
    )

    events = []
    rounds = 0
    for round_number in range(1, MAX_ROUNDS + 1):
        _tick_cooldowns(fighter_a)
        _tick_cooldowns(fighter_b)

        move_a = _select_move(fighter_a, fighter_b, tactic_a)
        move_b = _select_move(fighter_b, fighter_a, tactic_b)
        fallback_a = None
        fallback_b = None
        if not _available(fighter_a, move_a):
            fallback_a = move_a
            move_a = "basic_attack"
        if not _available(fighter_b, move_b):
            fallback_b = move_b
            move_b = "basic_attack"

        fighter_a.round_guarding = move_a == "guard"
        fighter_b.round_guarding = move_b == "guard"
        first, second = _initiative(fighter_a, fighter_b, rng)

        for actor in (first, second):
            defender = fighter_b if actor.side == "a" else fighter_a
            if actor.hp == 0 or defender.hp == 0:
                break
            move = move_a if actor.side == "a" else move_b
            fallback = fallback_a if actor.side == "a" else fallback_b
            events.append(
                _apply_move(
                    round_number, actor, defender, move, fallback, rng, version
                )
            )
            if fighter_a.hp == 0 or fighter_b.hp == 0:
                break

        fighter_a.guarding = fighter_a.round_guarding
        fighter_b.guarding = fighter_b.round_guarding
        rounds = round_number
        if fighter_a.hp == 0 or fighter_b.hp == 0:
            break

    final_hp = {"a": fighter_a.hp, "b": fighter_b.hp}
    if fighter_a.hp == 0 and fighter_b.hp == 0:
        winner = None
        result = "ko"
    elif fighter_a.hp == 0:
        winner = "b"
        result = "ko"
    elif fighter_b.hp == 0:
        winner = "a"
        result = "ko"
    else:
        winner = _decide_winner(fighter_a, fighter_b, rng)
        result = "decision"

    replay_hash = compute_replay_hash(events)
    return Replay(
        ruleset_version=version,
        seed=normalized_seed,
        events=events,
        rounds=rounds,
        winner=winner,
        result=result,
        final_hp=final_hp,
        replay_hash=replay_hash,
    )
