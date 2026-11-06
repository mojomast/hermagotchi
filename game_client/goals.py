"""Thin HTTP client helpers for owner-authorised Hermagotchi goals.

The record validation and zero-token proposer live in :mod:`agent_policy` so the
plugin tool layer and the hosted client share one implementation. No art assets
or PNG files are loaded here; cosmetic goals carry catalog item ids as strings.
"""

from __future__ import annotations

from typing import Any, Mapping

try:  # Imported as ``hermagotchi.game_client.goals``.
    from ..agent_policy import (
        ALLOWED_SUMMARY_KEYS,
        GOAL_TYPES,
        Goal,
        goal_progress,
        make_goal,
        propose_goal,
        sanitize_summary,
        validate_goal,
    )
except ImportError:  # Imported as ``game_client.goals`` from a checkout.
    from agent_policy import (
        ALLOWED_SUMMARY_KEYS,
        GOAL_TYPES,
        Goal,
        goal_progress,
        make_goal,
        propose_goal,
        sanitize_summary,
        validate_goal,
    )

from .errors import GameClientError


def _normalise_goal(
    goal: Goal | Mapping[str, Any] | None = None,
    explicit: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Goal:
    values: dict[str, Any] = {}
    if isinstance(goal, Goal):
        values.update(goal.to_dict())
    elif isinstance(goal, Mapping):
        values.update(goal)
    if explicit:
        values.update(explicit)
    values.update({key: val for key, val in kwargs.items() if val is not None})
    return Goal.from_dict(values)


def _validated(record: Goal) -> Goal:
    code = validate_goal(record)
    if code != "ok":
        raise GameClientError(code, "Goal record is not valid.")
    return record


class GoalsClient:
    """Bounded wrapper around a configured :class:`game_client.GameClient`."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def list(self) -> dict[str, Any]:
        return self.client._request("GET", "/goals")

    list_goals = list

    def get(self) -> dict[str, Any]:
        result = self.list()
        if isinstance(result, Mapping) and isinstance(result.get("goal"), Mapping):
            return dict(result["goal"])
        goals = result.get("goals") if isinstance(result, Mapping) else None
        if isinstance(goals, list) and goals:
            return dict(goals[0])
        return {}

    get_goal = get

    def set(
        self,
        goal: Goal | Mapping[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        record = _validated(_normalise_goal(goal, kwargs))
        return self.client._request(
            "POST",
            "/goals",
            json_body=record.to_dict(),
            action="goals.set",
            idempotency_key=idempotency_key,
        )

    set_goal = set

    def clear(self, *, idempotency_key: str | None = None) -> dict[str, Any]:
        return self.client._request(
            "DELETE",
            "/goals",
            json_body={},
            action="goals.clear",
            idempotency_key=idempotency_key,
        )

    clear_goal = clear


def list_goals(client: Any) -> dict[str, Any]:
    return GoalsClient(client).list()


def get_goal(client: Any) -> dict[str, Any]:
    return GoalsClient(client).get()


def set_goal(
    client: Any,
    goal: Goal | Mapping[str, Any] | None = None,
    *,
    idempotency_key: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return GoalsClient(client).set(goal, idempotency_key=idempotency_key, **kwargs)


def clear_goal(client: Any, *, idempotency_key: str | None = None) -> dict[str, Any]:
    return GoalsClient(client).clear(idempotency_key=idempotency_key)


__all__ = [
    "ALLOWED_SUMMARY_KEYS",
    "GOAL_TYPES",
    "Goal",
    "GoalsClient",
    "clear_goal",
    "get_goal",
    "goal_progress",
    "list_goals",
    "make_goal",
    "propose_goal",
    "sanitize_summary",
    "set_goal",
    "validate_goal",
]
