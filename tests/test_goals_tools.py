"""End-to-end tool tests for policy-checked owner goals (HGT-W5-L)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import schemas  # noqa: E402
import tools  # noqa: E402


def _client(**policy):
    return tools.FakeGameClient(policy=policy)


def _set_goal(client, key="goal-1", **overrides):
    args = {
        "op": "set",
        "target_type": "cosmetic",
        "target_id": "hat.binary_crown",
        "spending_limit_bits": 2000,
        "max_battles": 3,
        "idempotency_key": key,
    }
    args.update(overrides)
    return tools.handle_tool("hermagotchi_goals", args, client=client)


def test_tool_count_and_goal_ops_remain_frozen() -> None:
    assert len(schemas.TOOL_NAMES) == 8
    assert len(schemas.TOOL_SCHEMAS) == 8
    assert schemas.TOOL_SCHEMAS["hermagotchi_goals"]["properties"]["op"]["enum"] == [
        "list",
        "set",
        "clear",
    ]
    assert "goal" in schemas.TOOL_SCHEMAS["hermagotchi_status"]["properties"]["op"][
        "enum"
    ]


def test_goals_list_starts_empty() -> None:
    reply = tools.handle_tool("hermagotchi_goals", {"op": "list"}, client=_client())

    assert reply["ok"] is True
    assert reply["data"]["goals"] == []


def test_default_policy_fails_closed_for_goal_mutations() -> None:
    reply = _set_goal(_client())

    assert reply["ok"] is False
    assert reply["error_code"] == "network_disabled"

    cleared = tools.handle_tool(
        "hermagotchi_goals",
        {"op": "clear", "idempotency_key": "clear-1"},
        client=_client(),
    )
    assert cleared["ok"] is False
    assert cleared["error_code"] == "network_disabled"


def test_human_owner_can_set_and_status_reports_the_goal() -> None:
    client = _client(network_enabled=True)
    reply = _set_goal(client)

    assert reply["ok"] is True, reply
    goal = reply["data"]["goal"]
    assert goal["type"] == "cosmetic"
    assert goal["target_id"] == "hat.binary_crown"
    assert goal["chosen_by"] == "human"
    assert goal["spending_limit_bits"] == 2000
    assert goal["max_battles"] == 3
    assert goal["expires_at"] is not None
    assert goal["chosen_at"]

    listed = tools.handle_tool("hermagotchi_goals", {"op": "list"}, client=client)
    assert listed["data"]["goals"] == [goal]

    status = tools.handle_tool("hermagotchi_status", {"op": "goal"}, client=client)
    assert status["ok"] is True
    assert status["data"]["goal"] == goal


def test_agent_goal_selection_requires_explicit_permission() -> None:
    agent = _client(network_enabled=True, mode="agent")
    denied = _set_goal(agent)

    assert denied["ok"] is False
    assert denied["error_code"] == "goal_selection_disabled"

    allowed = _client(
        network_enabled=True,
        mode="agent",
        allow_goal_selection=True,
    )
    reply = _set_goal(allowed, target_type="rank", target_id="rank.top_100")
    assert reply["ok"] is True
    assert reply["data"]["goal"]["chosen_by"] == "agent"
    assert reply["data"]["goal"]["type"] == "rank"


def test_goal_set_validates_inputs_and_replays_idempotently() -> None:
    client = _client(network_enabled=True)

    bad_type = _set_goal(client, key="bad-type", target_type="wallet")
    assert bad_type["ok"] is False
    assert bad_type["error_code"] == "invalid_arguments"

    bad_target = _set_goal(client, key="bad-target", target_id="https://example.invalid/x")
    assert bad_target["ok"] is False
    assert bad_target["error_code"] == "invalid_arguments"

    first = _set_goal(client, key="stable-key")
    second = _set_goal(client, key="stable-key", target_id="front.pixel_badge")

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["correlation_id"] == first["correlation_id"]
    assert second["data"]["goal"]["target_id"] == "hat.binary_crown"


def test_clear_goal_is_policy_checked_and_idempotent() -> None:
    client = _client(network_enabled=True)
    assert _set_goal(client)["ok"] is True

    cleared = tools.handle_tool(
        "hermagotchi_goals",
        {"op": "clear", "idempotency_key": "clear-key"},
        client=client,
    )
    assert cleared["ok"] is True
    assert cleared["data"] == {"goal": None, "cleared": True}

    status = tools.handle_tool("hermagotchi_status", {"op": "goal"}, client=client)
    assert status["data"]["goal"] is None

    replay = tools.handle_tool(
        "hermagotchi_goals",
        {"op": "clear", "idempotency_key": "clear-key"},
        client=client,
    )
    assert replay["correlation_id"] == cleared["correlation_id"]


def test_mutating_shop_and_battle_ops_fail_closed_offline() -> None:
    client = _client()

    bought = tools.handle_tool(
        "hermagotchi_shop",
        {"op": "buy", "item_id": "hat.binary_crown", "idempotency_key": "buy-1"},
        client=client,
    )
    assert bought["ok"] is False
    assert bought["error_code"] == "network_disabled"

    practiced = tools.handle_tool(
        "hermagotchi_battle",
        {"op": "practice", "idempotency_key": "practice-1"},
        client=tools.FakeGameClient(
            policy={"network_enabled": True, "agent_autonomy_enabled": False}
        ),
    )
    assert practiced["ok"] is False
    assert practiced["error_code"] == "autonomy_disabled"
