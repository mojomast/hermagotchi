"""Owner policy gate for outbound game actions.

``PolicyGate`` is the small, frozen four-switch client gate used by
:class:`game_client.GameClient`. The complete owner policy (budgets, goal
selection, cosmetic purchases and ranked approval) lives in
:mod:`agent_policy`; this module re-exports it as a thin client so callers have
one import location.
"""

from __future__ import annotations

from typing import Any, Mapping

from .errors import PolicyDeniedError

try:  # Imported as ``hermagotchi.game_client.policy``.
    from ..agent_policy import (
        DEFAULT_POLICY as _AGENT_DEFAULT_POLICY,
        Policy as AgentPolicy,
        check_budget as _check_budget,
        check_mutation as _check_mutation,
    )
except ImportError:  # Imported as ``game_client.policy`` from a checkout.
    from agent_policy import (
        DEFAULT_POLICY as _AGENT_DEFAULT_POLICY,
        Policy as AgentPolicy,
        check_budget as _check_budget,
        check_mutation as _check_mutation,
    )

#: Full contracts-v1 owner policy defaults (14 fields).
DEFAULT_POLICY: dict[str, Any] = dict(_AGENT_DEFAULT_POLICY.as_dict())

#: Minimal defaults kept for the existing four-switch transport gate.
_GATE_DEFAULTS: dict[str, Any] = {
    "mode": "human",
    "network_enabled": False,
    "autonomy_enabled": False,
    "chat_enabled": False,
}

CHAT_MUTATIONS = frozenset(
    {"social.send", "chat.send", "social.taunt", "chat.taunt"}
)
AUTONOMY_MUTATIONS = frozenset(
    {
        "autonomy.battle",
        "autonomy.challenge",
        "autonomy.purchase",
    }
)


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


class PolicyGate:
    """Small, explicit gate matching the frozen contracts-v1 defaults."""

    def __init__(self, policy: Mapping[str, Any] | None = None) -> None:
        values = dict(_GATE_DEFAULTS)
        if policy:
            raw = dict(policy)
            if "autonomy_enabled" not in raw and "agent_autonomy_enabled" in raw:
                raw["autonomy_enabled"] = raw["agent_autonomy_enabled"]
            if "chat_enabled" not in raw and "agent_chat_enabled" in raw:
                raw["chat_enabled"] = raw["agent_chat_enabled"]
            raw.pop("agent_autonomy_enabled", None)
            raw.pop("agent_chat_enabled", None)
            values.update(raw)
        mode = values.get("mode", "human")
        values["mode"] = str(mode) if isinstance(mode, str) else "human"
        for key in ("network_enabled", "autonomy_enabled", "chat_enabled"):
            values[key] = _as_bool(values.get(key, False))
        self._values = values

    @property
    def mode(self) -> str:
        return self._values["mode"]

    @property
    def network_enabled(self) -> bool:
        return self._values["network_enabled"]

    @property
    def autonomy_enabled(self) -> bool:
        return self._values["autonomy_enabled"]

    @property
    def chat_enabled(self) -> bool:
        return self._values["chat_enabled"]

    def as_dict(self) -> dict[str, Any]:
        return dict(self._values)

    def snapshot(self) -> dict[str, Any]:
        return self.as_dict()

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def require_network(self, action: str = "mutation") -> None:
        if not self.network_enabled:
            raise PolicyDeniedError(
                "network_disabled",
                f"Network is disabled; enable network_enabled before {action}.",
            )

    def require_autonomy(self, action: str = "autonomous action") -> None:
        if not self.autonomy_enabled:
            raise PolicyDeniedError(
                "autonomy_disabled",
                f"Agent autonomy is disabled; enable autonomy_enabled before {action}.",
            )

    def require_chat(self, action: str = "chat action") -> None:
        if not self.chat_enabled:
            raise PolicyDeniedError(
                "chat_disabled",
                f"Agent chat is disabled; enable chat_enabled before {action}.",
            )

    def check_mutation(self, action: str) -> None:
        self.require_network(action)
        if action in CHAT_MUTATIONS:
            self.require_chat(action)
        if action in AUTONOMY_MUTATIONS:
            self.require_autonomy(action)


# -- thin client re-exports ------------------------------------------------
Policy = AgentPolicy


def policy_from_mapping(value: Mapping[str, Any] | AgentPolicy | None = None) -> AgentPolicy:
    return AgentPolicy.from_mapping(value)


def check_mutation(
    policy: AgentPolicy | Mapping[str, Any] | None, action: str
) -> str:
    """Return ``"ok"`` or a stable error code for one mutation action."""

    return _check_mutation(policy, action)


def check_budget(
    policy: AgentPolicy | Mapping[str, Any] | None, kind: str, used: int
) -> str:
    return _check_budget(policy, kind, used)


__all__ = [
    "AgentPolicy",
    "AUTONOMY_MUTATIONS",
    "CHAT_MUTATIONS",
    "DEFAULT_POLICY",
    "Policy",
    "PolicyGate",
    "check_budget",
    "check_mutation",
    "policy_from_mapping",
]
