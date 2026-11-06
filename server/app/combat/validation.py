import copy
import re
from collections.abc import Mapping

from .ruleset import (
    ALLOWED_MOVES,
    ALLOWED_PREDICATES,
    ALLOWED_STANCES,
    ALLOWED_TACTIC_FIELDS,
    NEUTRAL_TACTIC,
    RULESET_VERSION,
    SPECIES_STATS,
    Ruleset,
)

EMOTE_RE = re.compile(r"^emote\.[A-Za-z0-9][A-Za-z0-9_.-]{0,56}$")


class CombatError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self):
        return {"code": self.code, "message": self.message}


class TacticValidationError(CombatError):
    pass


class RulesetError(CombatError):
    pass


def normalize_ruleset(ruleset):
    if ruleset is None:
        return RULESET_VERSION
    if isinstance(ruleset, Ruleset):
        version = ruleset.version
    elif isinstance(ruleset, str):
        version = ruleset
    elif isinstance(ruleset, Mapping):
        version = ruleset.get("ruleset_version", ruleset.get("version"))
    else:
        version = getattr(
            ruleset, "ruleset_version", getattr(ruleset, "version", None)
        )
    if version != RULESET_VERSION:
        raise RulesetError(
            "ruleset_unsupported",
            f"unsupported ruleset: {version!r}",
        )
    return RULESET_VERSION


def normalize_pet(pet):
    if isinstance(pet, Mapping):
        species = pet.get("species")
    else:
        species = getattr(pet, "species", None)
    if not isinstance(species, str):
        raise CombatError("pet_invalid", "pet must declare a species")
    if species not in SPECIES_STATS:
        raise CombatError("species_unknown", f"unknown species: {species!r}")
    return species


def _reject(code, message):
    raise TacticValidationError(code, message)


def _validate_predicate(when):
    if not isinstance(when, Mapping) or len(when) != 1:
        _reject("tactic_predicate_invalid", "when must contain exactly one predicate")
    key, value = next(iter(when.items()))
    if key not in ALLOWED_PREDICATES:
        _reject("tactic_predicate_unknown", f"unknown predicate: {key!r}")
    if key == "self_hp_lte_pct":
        if isinstance(value, bool) or not isinstance(value, int):
            _reject("tactic_predicate_invalid", "self_hp_lte_pct must be an integer")
        if value < 0 or value > 100:
            _reject("tactic_predicate_invalid", "self_hp_lte_pct must be 0..100")
    elif key in {"opponent_guarding", "special_ready", "always"}:
        if not isinstance(value, bool):
            _reject("tactic_predicate_invalid", f"{key} must be a boolean")
    return {key: value}


def _validate_action(action):
    if not isinstance(action, Mapping):
        _reject("tactic_action_invalid", "action must be an object")
    if set(action.keys()) != {"when", "move"}:
        _reject(
            "tactic_action_invalid",
            "action must contain exactly when and move",
        )
    move = action["move"]
    if not isinstance(move, str) or move not in ALLOWED_MOVES:
        _reject("tactic_move_unknown", f"unknown move: {move!r}")
    return {"when": _validate_predicate(action["when"]), "move": move}


def validate_tactic_card(card, ruleset_version=RULESET_VERSION):
    if card is None:
        return copy.deepcopy(NEUTRAL_TACTIC)
    if not isinstance(card, Mapping):
        _reject("tactic_not_object", "tactic card must be an object")
    unknown = set(card.keys()) - ALLOWED_TACTIC_FIELDS
    if unknown:
        _reject("tactic_field_unknown", f"unknown tactic fields: {sorted(unknown)}")

    declared_ruleset = card.get("ruleset_version", ruleset_version)
    if declared_ruleset != ruleset_version:
        _reject(
            "tactic_ruleset_mismatch",
            f"tactic ruleset {declared_ruleset!r} does not match {ruleset_version!r}",
        )

    stance = card.get("stance", "balanced")
    if not isinstance(stance, str) or stance not in ALLOWED_STANCES:
        _reject("tactic_stance_invalid", f"unknown stance: {stance!r}")

    actions = card.get("actions")
    if not isinstance(actions, list):
        _reject("tactic_actions_invalid", "actions must be a list")
    if len(actions) > 4:
        _reject("tactic_too_many_actions", "tactic cards allow at most 4 actions")

    normalized = {
        "ruleset_version": ruleset_version,
        "stance": stance,
        "actions": [_validate_action(action) for action in actions],
    }

    if "emote_id" in card:
        emote_id = card["emote_id"]
        if not isinstance(emote_id, str) or not EMOTE_RE.fullmatch(emote_id):
            _reject("tactic_emote_invalid", f"invalid emote_id: {emote_id!r}")
        normalized["emote_id"] = emote_id

    return normalized
