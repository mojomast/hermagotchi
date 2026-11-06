"""Owner policy model and the single mutation gate for Hermagotchi.

The defaults mirror the frozen contracts-v1 safe configuration: the human owns
the pet, networking is off, agent autonomy and chat are off, every budget is
zero, goal selection and cosmetic purchases need explicit opt-in, and ranked
play needs human approval.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any, Iterator, Mapping

VALID_MODES = frozenset({"human", "agent", "co-op"})
_MODE_ALIASES = {"coop": "co-op", "co_op": "co-op"}

# Actions that are pure reads and never touch owner state.
READ_ACTIONS = frozenset(
    {
        "status.me",
        "status.pet",
        "status.wallet",
        "status.goal",
        "status.inbox",
        "status.health",
        "goals.list",
        "challenge.list_opponents",
        "battle.get",
        "battle.replay",
        "shop.catalog",
        "shop.inventory",
        "social.read",
        "meta.leaderboard",
        "meta.bounties",
    }
)
_READ_LEAVES = frozenset(
    {
        "me",
        "pet",
        "wallet",
        "goal",
        "inbox",
        "health",
        "list",
        "list_opponents",
        "get",
        "replay",
        "catalog",
        "inventory",
        "read",
        "leaderboard",
        "bounties",
    }
)

CHAT_ACTIONS = frozenset({"social.send", "chat.send", "message.send"})
NETWORK_ONLY_ACTIONS = frozenset(
    {"social.block", "social.report", "moderation.report"}
)
GOAL_ACTIONS = frozenset(
    {
        "goals.set",
        "goals.clear",
        "goals.select",
        "goal.set",
        "goal.clear",
        "goal.select",
    }
)
PURCHASE_ACTIONS = frozenset(
    {
        "shop.buy",
        "shop.purchase",
        "shop.equip",
        "purchase",
        "buy",
        "cosmetic.purchase",
    }
)
RANKED_ACTIONS = frozenset(
    {
        "battle.ranked",
        "challenge.invite.ranked",
        "challenge.respond.ranked",
        "ranked.match",
    }
)
AUTONOMY_ACTIONS = frozenset(
    {
        "pet.adopt",
        "pet.rename",
        "pet.set_mode",
        "pet.care",
        "challenge.invite",
        "challenge.respond",
        "challenge.submit_tactics",
        "battle.practice",
        "battle.claim",
        "meta.claim_bounty",
        "autonomy.battle",
        "autonomy.challenge",
        "autonomy.purchase",
    }
)

_ACTION_ALIASES = {
    "care": "pet.care",
    "adopt": "pet.adopt",
    "rename": "pet.rename",
    "set_mode": "pet.set_mode",
    "chat.send": "social.send",
    "message.send": "social.send",
    "report": "social.report",
    "block": "social.block",
    "purchase": "shop.buy",
    "buy": "shop.buy",
    "equip": "shop.equip",
    "claim_bounty": "meta.claim_bounty",
    "goals_set": "goals.set",
    "goals_clear": "goals.clear",
    "goal_set": "goals.set",
    "goal_clear": "goals.clear",
    "autonomy.purchase": "shop.buy",
}


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number >= 0 else default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number >= 0 else default


@dataclass(frozen=True)
class Policy:
    """Typed owner policy with contracts-v1 safe defaults."""

    mode: str = "human"
    network_enabled: bool = False
    agent_autonomy_enabled: bool = False
    agent_chat_enabled: bool = False
    agent_chat_send_per_day: int = 0
    agent_challenges_per_day: int = 0
    agent_ranked_matches_per_day: int = 0
    agent_inference_decisions_per_day: int = 0
    llm_budget_usd_per_day: float = 0.0
    allow_goal_selection: bool = False
    allow_cosmetic_purchases: bool = False
    require_human_approval_for_ranked: bool = True
    quiet_hours_local: tuple[str, str] = ("22:00", "08:00")

    def __post_init__(self) -> None:
        mode = str(self.mode or "human").strip().lower()
        mode = _MODE_ALIASES.get(mode, mode)
        if mode not in VALID_MODES:
            mode = "human"
        object.__setattr__(self, "mode", mode)
        for name in (
            "network_enabled",
            "agent_autonomy_enabled",
            "agent_chat_enabled",
            "allow_goal_selection",
            "allow_cosmetic_purchases",
            "require_human_approval_for_ranked",
        ):
            object.__setattr__(self, name, _as_bool(getattr(self, name)))
        for name in (
            "agent_chat_send_per_day",
            "agent_challenges_per_day",
            "agent_ranked_matches_per_day",
            "agent_inference_decisions_per_day",
        ):
            object.__setattr__(self, name, _as_int(getattr(self, name)))
        object.__setattr__(
            self, "llm_budget_usd_per_day", _as_float(self.llm_budget_usd_per_day)
        )
        quiet = self.quiet_hours_local
        if isinstance(quiet, str):
            quiet = tuple(part.strip() for part in quiet.split(",") if part.strip())
        else:
            quiet = tuple(str(part).strip() for part in quiet)
        if len(quiet) != 2:
            quiet = ("22:00", "08:00")
        object.__setattr__(self, "quiet_hours_local", quiet)

    # -- mapping conveniences -------------------------------------------
    def as_dict(self) -> dict[str, Any]:
        data = {field.name: getattr(self, field.name) for field in fields(self)}
        data["quiet_hours_local"] = list(self.quiet_hours_local)
        return data

    to_dict = as_dict

    def get(self, key: str, default: Any = None) -> Any:
        return self.as_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.as_dict())

    def keys(self):
        return self.as_dict().keys()

    def values(self):
        return self.as_dict().values()

    def items(self):
        return self.as_dict().items()

    def replace(self, **changes: Any) -> "Policy":
        return replace(self, **changes)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | "Policy" | None = None) -> "Policy":
        if isinstance(value, cls):
            return value
        raw: dict[str, Any] = dict(value or {})
        if "autonomy_enabled" in raw and "agent_autonomy_enabled" not in raw:
            raw["agent_autonomy_enabled"] = raw["autonomy_enabled"]
        if "chat_enabled" in raw and "agent_chat_enabled" not in raw:
            raw["agent_chat_enabled"] = raw["chat_enabled"]
        valid = {field.name for field in fields(cls)}
        return cls(**{key: val for key, val in raw.items() if key in valid})

    from_dict = from_mapping


DEFAULT_POLICY = Policy()
DEFAULT_POLICY_DICT = DEFAULT_POLICY.as_dict()


def default_policy() -> Policy:
    return DEFAULT_POLICY


def _coerce_policy(policy: Policy | Mapping[str, Any] | None) -> Policy:
    if isinstance(policy, Policy):
        return policy
    return Policy.from_mapping(policy)


def _normalise_action(action: str) -> str:
    value = str(action or "").strip().lower()
    if not value:
        return ""
    if value.startswith("hermagotchi_"):
        value = value[len("hermagotchi_") :]
    if value.startswith("hermagotchi."):
        value = value[len("hermagotchi.") :]
    value = value.replace(":", ".")
    return _ACTION_ALIASES.get(value, value)


def _is_read(action: str) -> bool:
    if action in READ_ACTIONS:
        return True
    if action.startswith(("local.",)):
        return False
    leaf = action.rsplit(".", 1)[-1]
    return leaf in _READ_LEAVES


def _is_chat(action: str) -> bool:
    return action in CHAT_ACTIONS or action.endswith(".send")


def _is_goal(action: str) -> bool:
    return action in GOAL_ACTIONS or action.startswith(("goals.", "goal."))


def _is_purchase(action: str) -> bool:
    return action in PURCHASE_ACTIONS or action.startswith(("shop.", "cosmetic."))


def _is_ranked(action: str) -> bool:
    return action in RANKED_ACTIONS or action.endswith(".ranked")


def check_mutation(
    policy: Policy | Mapping[str, Any] | None, action: str
) -> str:
    """Return ``"ok"`` when a mutation is allowed, else a stable error code.

    The gate is ordered so a mutation first fails closed while networking is
    disabled, then applies the specific owner opt-in (chat, cosmetic spend,
    goal selection, ranked approval) and finally the general autonomy switch.
    """

    active = _coerce_policy(policy)
    act = _normalise_action(action)
    if not act:
        return "invalid_action"

    # Local-only fake/offline operations such as pet care never leave the box.
    if act.startswith("local."):
        return "ok"
    if _is_read(act):
        return "ok"

    if not active.network_enabled:
        return "network_disabled"

    if _is_chat(act):
        return "ok" if active.agent_chat_enabled else "chat_disabled"

    if act in NETWORK_ONLY_ACTIONS:
        return "ok"

    if _is_goal(act):
        if act.endswith(".human"):
            return "ok" if active.mode in {"human", "co-op"} else "goal_selection_disabled"
        # Agent-selected goals need an explicit owner opt-in.
        return "ok" if active.allow_goal_selection else "goal_selection_disabled"

    if _is_ranked(act):
        if active.require_human_approval_for_ranked:
            return "human_approval_required"
        return "ok" if active.agent_autonomy_enabled else "autonomy_disabled"

    if _is_purchase(act):
        return (
            "ok"
            if active.allow_cosmetic_purchases
            else "cosmetic_purchases_disabled"
        )

    if act in AUTONOMY_ACTIONS or act.startswith("autonomy."):
        return "ok" if active.agent_autonomy_enabled else "autonomy_disabled"

    # Unknown mutating actions fail closed unless autonomy was granted.
    return "ok" if active.agent_autonomy_enabled else "autonomy_disabled"


_BUDGET_FIELDS = {
    "chat": "agent_chat_send_per_day",
    "challenges": "agent_challenges_per_day",
    "ranked": "agent_ranked_matches_per_day",
    "inference": "agent_inference_decisions_per_day",
}


def check_budget(
    policy: Policy | Mapping[str, Any] | None, kind: str, used: int
) -> str:
    """Return ``"ok"`` or ``"budget_exhausted"`` for a per-day budget kind."""

    active = _coerce_policy(policy)
    field_name = _BUDGET_FIELDS.get(str(kind).strip().lower())
    if field_name is None:
        return "unknown_budget"
    limit = int(getattr(active, field_name))
    return "budget_exhausted" if int(used) >= limit else "ok"


__all__ = [
    "AUTONOMY_ACTIONS",
    "CHAT_ACTIONS",
    "DEFAULT_POLICY",
    "DEFAULT_POLICY_DICT",
    "GOAL_ACTIONS",
    "NETWORK_ONLY_ACTIONS",
    "Policy",
    "PURCHASE_ACTIONS",
    "RANKED_ACTIONS",
    "READ_ACTIONS",
    "check_budget",
    "check_mutation",
    "default_policy",
]
