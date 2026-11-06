"""HGT-W13-B: inbox, taunt and DM social coverage on the frozen eight tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_policy import (  # noqa: E402
    DEFAULT_POLICY,
    Policy,
    check_budget,
    check_mutation,
)
from game_client import GameClient, PolicyDeniedError  # noqa: E402
from game_client.social import SocialAPI  # noqa: E402
from schemas import OP_ENUMS, TOOL_NAMES, TOOL_SCHEMAS  # noqa: E402
import tools  # noqa: E402

ONLINE_CHAT = {
    "network_enabled": True,
    "agent_chat_enabled": True,
    "agent_autonomy_enabled": True,
}


def _client(policy: dict | None = None) -> tools.FakeGameClient:
    return tools.FakeGameClient(policy=policy)


def _send(client, **arguments):
    payload = {"op": "send", "idempotency_key": "w13-send"}
    payload.update(arguments)
    return tools.handle_tool("hermagotchi_social", payload, client=client)


def _taunt(client, key: str = "w13-taunt", **arguments):
    payload = {"op": "taunt", "idempotency_key": key}
    payload.update(arguments)
    return tools.handle_tool("hermagotchi_social", payload, client=client)


def _make_live_client(handler, policy: dict) -> GameClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://testserver")
    return GameClient(
        base_url="http://testserver/v1",
        policy=policy,
        http_client=http_client,
        max_retries=0,
        sleep=lambda _seconds: None,
    )


def test_catalog_stays_at_eight_tools_with_extended_social_ops() -> None:
    assert len(TOOL_NAMES) == 8
    assert len(TOOL_SCHEMAS) == 8
    assert OP_ENUMS["hermagotchi_social"] == [
        "read",
        "send",
        "block",
        "report",
        "inbox",
        "taunt",
        "friends",
        "history",
    ]

    properties = TOOL_SCHEMAS["hermagotchi_social"]["properties"]
    for field in (
        "channel_id",
        "body",
        "target",
        "target_id",
        "reason",
        "match_id",
        "phase",
        "lobby",
    ):
        assert field in properties
    assert properties["phase"]["enum"] == ["pre", "post"]
    assert properties["lobby"]["type"] == "boolean"


def test_inbox_is_an_offline_read_with_dm_and_mention_shape() -> None:
    client = _client()

    reply = tools.handle_tool("hermagotchi_social", {"op": "inbox"}, client=client)

    assert reply["ok"] is True, reply
    assert reply["data"]["unread"] == []
    assert reply["data"]["mentions"] == []
    assert reply["data"]["count"] == 0
    assert client.chat_usage == {"lobby": 0, "dm": 0}


def test_send_lobby_requires_network_then_chat() -> None:
    offline = _send(_client(), body="hello", lobby=True)
    assert offline["ok"] is False
    assert offline["error_code"] == "network_disabled"

    no_chat = _send(
        _client({"network_enabled": True}),
        body="hello",
        lobby=True,
    )
    assert no_chat["ok"] is False
    assert no_chat["error_code"] == "chat_disabled"

    allowed = _send(_client(ONLINE_CHAT), body="hello", lobby=True)
    assert allowed["ok"] is True, allowed
    assert allowed["data"]["message"]["channel_id"] == "lobby"


def test_send_dm_by_target_synthesizes_sorted_dm_channel() -> None:
    client = _client(ONLINE_CHAT)

    reply = _send(client, target="Rival", body="your crown is crooked")

    assert reply["ok"] is True, reply
    message = reply["data"]["message"]
    assert message["channel_id"] == "dm:Rival:self"
    assert message["target_id"] == "Rival"
    assert message["dm"] is True
    assert client.chat_usage == {"lobby": 0, "dm": 1}


def test_send_dm_uses_pet_identity_and_requires_dm_budget() -> None:
    client = _client(ONLINE_CHAT)
    adopted = tools.handle_tool(
        "hermagotchi_pet",
        {
            "op": "adopt",
            "species": "byteblob",
            "name": "Nib",
            "idempotency_key": "w13-adopt",
        },
        client=client,
    )
    assert adopted["ok"] is True
    pet_id = client.pet["pet_id"]

    reply = _send(client, target="Rival", body="hello")
    assert reply["ok"] is True, reply
    assert reply["data"]["message"]["channel_id"] == (
        "dm:" + ":".join(sorted([pet_id, "Rival"]))
    )

    capped = _client({**ONLINE_CHAT, "agent_chat_dm_per_day": 0})
    denied = _send(capped, target="Rival", body="hello")
    assert denied["ok"] is False
    assert denied["error_code"] == "budget_exhausted"


def test_taunt_denies_map_to_server_chat_codes() -> None:
    offline = _taunt(
        _client(),
        match_id="match_1",
        body="nice pet",
        phase="pre",
    )
    assert offline["ok"] is False
    assert offline["error_code"] == "network_disabled"

    no_chat = _taunt(
        _client({"network_enabled": True}),
        match_id="match_1",
        body="nice pet",
        phase="pre",
    )
    assert no_chat["ok"] is False
    assert no_chat["error_code"] == "chat.disabled"

    capped = _taunt(
        _client({**ONLINE_CHAT, "agent_chat_lobby_per_day": 0}),
        match_id="match_1",
        body="nice pet",
        phase="pre",
    )
    assert capped["ok"] is False
    assert capped["error_code"] == "chat.daily_cap"


def test_taunt_requires_match_id_body_and_phase() -> None:
    client = _client(ONLINE_CHAT)

    assert _taunt(client, body="hello", phase="pre")["error_code"] == (
        "invalid_arguments"
    )
    assert _taunt(client, match_id="match_1", phase="pre")["error_code"] == (
        "invalid_arguments"
    )
    assert _taunt(
        client,
        match_id="match_1",
        body="hello",
        phase="during",
    )["error_code"] == "invalid_arguments"


def test_taunt_returns_message_and_match_context_stub() -> None:
    client = _client(ONLINE_CHAT)

    reply = _taunt(
        client,
        match_id="match_9",
        body="that scarf lost the match",
        phase="post",
    )

    assert reply["ok"] is True, reply
    message = reply["data"]["message"]
    assert message["channel_id"] == "match:match_9"
    assert message["match_id"] == "match_9"
    assert message["phase"] == "post"
    assert reply["data"]["match_context"] == {
        "match_id": "match_9",
        "phase": "post",
        "status": "stub",
        "opponent": None,
    }
    assert client.chat_usage == {"lobby": 1, "dm": 0}


def test_taunt_counts_against_lobby_budget() -> None:
    client = _client({**ONLINE_CHAT, "agent_chat_lobby_per_day": 1})

    first = _taunt(
        client,
        key="w13-taunt-1",
        match_id="match_1",
        body="first",
        phase="pre",
    )
    second = _taunt(
        client,
        key="w13-taunt-2",
        match_id="match_1",
        body="second",
        phase="pre",
    )

    assert first["ok"] is True, first
    assert second["ok"] is False
    assert second["error_code"] == "chat.daily_cap"


def test_block_and_report_remain_network_only_mutations() -> None:
    client = _client(ONLINE_CHAT)

    blocked = tools.handle_tool(
        "hermagotchi_social",
        {
            "op": "block",
            "target_id": "account_2",
            "idempotency_key": "w13-block",
        },
        client=client,
    )
    reported = tools.handle_tool(
        "hermagotchi_social",
        {
            "op": "report",
            "target_id": "account_2",
            "reason": "spam",
            "idempotency_key": "w13-report",
        },
        client=client,
    )

    assert blocked["ok"] is True and blocked["data"]["blocked"] == "account_2"
    assert reported["ok"] is True
    assert reported["data"]["report"]["status"] == "received"


def test_policy_helpers_cover_taunt_inbox_and_chat_budgets() -> None:
    assert check_mutation(DEFAULT_POLICY, "social.inbox") == "ok"
    assert check_mutation(DEFAULT_POLICY, "social.taunt") == "network_disabled"
    assert (
        check_mutation(Policy(network_enabled=True), "social.taunt")
        == "chat_disabled"
    )
    assert (
        check_mutation(
            Policy(network_enabled=True, agent_chat_enabled=True),
            "social.taunt",
        )
        == "ok"
    )
    assert check_budget(DEFAULT_POLICY, "chat", 20) == "budget_exhausted"
    assert check_budget(DEFAULT_POLICY, "lobby", 19) == "ok"
    assert check_budget(DEFAULT_POLICY, "dm", 10) == "budget_exhausted"


def test_live_client_inbox_and_taunt_paths() -> None:
    seen: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        seen.append((request.method, request.url.path, body))
        if request.url.path == "/v1/chat/inbox":
            return httpx.Response(
                200,
                json={"unread": [], "mentions": [], "count": 0},
            )
        return httpx.Response(
            201,
            json={"message": {"id": "msg_1"}, "match_context": {"match_id": "m1"}},
        )

    client = _make_live_client(handler, ONLINE_CHAT)

    assert client.inbox()["unread"] == []
    reply = client.taunt("m1", "gg", "post", idempotency_key="live-taunt")
    assert reply["match_context"]["match_id"] == "m1"

    assert seen[0] == ("GET", "/v1/chat/inbox", {})
    assert seen[1][0:2] == ("POST", "/v1/chat/taunt")
    assert seen[1][2]["match_id"] == "m1"
    assert seen[1][2]["body"] == "gg"
    assert seen[1][2]["phase"] == "post"
    assert seen[1][2]["idempotency_key"] == "live-taunt"


def test_live_client_dm_send_path_and_chat_gate() -> None:
    seen: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        seen.append((request.method, request.url.path, body))
        return httpx.Response(201, json={"message": {"id": "msg_dm"}})

    client = _make_live_client(handler, ONLINE_CHAT)
    result = client.send_message(
        target="Rival",
        body="hello",
        idempotency_key="live-dm",
    )

    assert result["message"]["id"] == "msg_dm"
    assert seen[0][0:2] == ("POST", "/v1/chat/dm")
    assert seen[0][2]["target"] == "Rival"
    assert seen[0][2]["body"] == "hello"

    no_chat = _make_live_client(handler, {"network_enabled": True})
    with pytest.raises(PolicyDeniedError) as excinfo:
        no_chat.send_message(target="Rival", body="hello")
    assert excinfo.value.code == "chat_disabled"


def test_social_api_wrappers_delegate_to_the_client() -> None:
    calls: list[str] = []

    class Stub:
        def inbox(self):
            calls.append("inbox")
            return {"unread": [], "mentions": []}

        def taunt(self, match_id, body, phase, *, idempotency_key=None):
            calls.append(f"taunt:{match_id}:{phase}")
            return {"message": {"match_id": match_id}}

        def send_message(self, *, body=None, target=None, idempotency_key=None):
            calls.append(f"send:{target}")
            return {"message": {"target": target}}

    api = SocialAPI(Stub())

    assert api.inbox()["unread"] == []
    assert api.taunt("m1", "gg", "pre")["message"]["match_id"] == "m1"
    assert api.send(target="Rival", body="hi")["message"]["target"] == "Rival"
    assert calls == ["inbox", "taunt:m1:pre", "send:Rival"]
