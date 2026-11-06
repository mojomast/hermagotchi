"""HGT-W14-B: friends and social history on the frozen eight tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_policy import DEFAULT_POLICY, Policy, check_mutation  # noqa: E402
from game_client import GameClient  # noqa: E402
from game_client.social import (  # noqa: E402
    SocialAPI,
    add_friend,
    list_friends,
    remove_friend,
    social_history,
)
from schemas import OP_ENUMS, TOOL_NAMES, TOOL_SCHEMAS  # noqa: E402
import tools  # noqa: E402

ONLINE = {"network_enabled": True}
ONLINE_CHAT = {
    "network_enabled": True,
    "agent_chat_enabled": True,
    "agent_autonomy_enabled": True,
}


def _client(policy: dict | None = None) -> tools.FakeGameClient:
    return tools.FakeGameClient(policy=policy)


def _call(client, op, **arguments):
    payload = {"op": op}
    payload.update(arguments)
    return tools.handle_tool("hermagotchi_social", payload, client=client)


def _friend(client, action, key="w14-friend", **arguments):
    payload = {"op": "friends", "action": action, "idempotency_key": key}
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


def test_catalog_stays_at_eight_tools_with_friends_and_history() -> None:
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
    assert OP_ENUMS["hermagotchi_challenge"] == [
        "list_opponents",
        "invite",
        "respond",
        "submit_tactics",
    ]

    social = TOOL_SCHEMAS["hermagotchi_social"]["properties"]
    assert social["action"]["enum"] == [
        "list",
        "add",
        "accept",
        "decline",
        "remove",
    ]
    assert social["filter"]["enum"] == [
        "all",
        "taunts_sent",
        "taunts_received",
        "mentions",
    ]
    assert {"target", "target_id"} <= set(social)


def test_friend_list_is_an_offline_read() -> None:
    client = _client()

    reply = _call(client, "friends")

    assert reply["ok"] is True, reply
    assert reply["data"]["friends"] == []
    assert reply["data"]["incoming"] == []
    assert reply["data"]["outgoing"] == []
    assert reply["data"]["count"] == 0


def test_friend_mutations_need_network_but_not_chat() -> None:
    offline = _friend(_client(), "add", target_id="Rival")
    assert offline["ok"] is False
    assert offline["error_code"] == "network_disabled"

    online = _friend(_client(ONLINE), "add", target_id="Rival")
    assert online["ok"] is True, online
    assert online["data"]["status"] == "pending"
    assert online["data"]["pending"] is True


def test_friend_add_reason_codes_and_pending_flow() -> None:
    client = _client(ONLINE)

    first = _friend(client, "add", key="w14-add-1", target_id="Rival")
    assert first["ok"] is True, first
    assert first["data"]["friend"]["target_id"] == "Rival"

    duplicate = _friend(client, "add", key="w14-add-2", target_id="Rival")
    assert duplicate["error_code"] == "friend.pending"

    incoming = _client(ONLINE)
    incoming.friend_incoming.add("Pal")
    accepted = _friend(incoming, "accept", key="w14-accept", target_id="Pal")
    assert accepted["ok"] is True, accepted
    assert accepted["data"]["status"] == "friends"
    assert incoming.friend_ids == {"Pal"}

    again = _friend(incoming, "add", key="w14-add-3", target_id="Pal")
    assert again["error_code"] == "friend.already"

    missing = _friend(incoming, "accept", key="w14-accept-2", target_id="Nobody")
    assert missing["error_code"] == "friend.not_found"


def test_friend_self_and_blocked_reason_codes() -> None:
    client = _client(ONLINE)

    itself = _friend(client, "add", target_id="self")
    assert itself["error_code"] == "friend.self"

    blocked = _call(
        client,
        "block",
        target_id="Rival",
        idempotency_key="w14-block",
    )
    assert blocked["ok"] is True
    denied = _friend(client, "add", key="w14-add-blocked", target_id="Rival")
    assert denied["error_code"] == "friend.blocked"


def test_friend_decline_and_remove_flow() -> None:
    client = _client(ONLINE)
    client.friend_incoming.add("Rival")

    declined = _friend(client, "decline", target_id="Rival")
    assert declined["ok"] is True, declined
    assert declined["data"]["status"] == "declined"
    assert client.friend_incoming == set()

    client.friend_ids.add("Pal")
    removed = _friend(client, "remove", key="w14-remove", target_id="Pal")
    assert removed["ok"] is True, removed
    assert removed["data"]["removed"] is True
    assert client.friend_ids == set()

    missing = _friend(client, "remove", key="w14-remove-2", target_id="Pal")
    assert missing["error_code"] == "friend.not_found"


def test_friend_invalid_action_and_target_are_rejected() -> None:
    client = _client(ONLINE)

    assert _friend(client, "invite", target_id="Rival")["error_code"] == (
        "invalid_arguments"
    )
    assert _friend(client, "add", target_id="")["error_code"] == "invalid_arguments"
    assert _friend(client, "add")["error_code"] == "invalid_arguments"


def test_history_is_a_filtered_read_and_records_sent_taunts() -> None:
    client = _client(ONLINE_CHAT)

    empty = _call(client, "history")
    assert empty["ok"] is True, empty
    assert empty["data"]["filter"] == "all"
    assert empty["data"]["items"] == []

    taunted = _call(
        client,
        "taunt",
        match_id="match_1",
        body="nice scarf",
        phase="pre",
        idempotency_key="w14-taunt",
    )
    assert taunted["ok"] is True, taunted

    all_items = _call(client, "history", filter="all")
    sent = _call(client, "history", filter="taunts_sent")
    received = _call(client, "history", filter="taunts_received")
    mentions = _call(client, "history", filter="mentions")

    assert all_items["data"]["count"] == 1
    assert sent["data"]["count"] == 1
    assert sent["data"]["items"][0]["match_id"] == "match_1"
    assert received["data"]["items"] == []
    assert mentions["data"]["items"] == []
    assert _call(client, "history", filter="everything")["error_code"] == (
        "invalid_arguments"
    )


def test_policy_treats_friend_reads_as_reads_and_mutations_as_network_only() -> None:
    assert check_mutation(DEFAULT_POLICY, "social.friends.list") == "ok"
    assert check_mutation(DEFAULT_POLICY, "social.history") == "ok"
    for action in (
        "social.friends.add",
        "social.friends.accept",
        "social.friends.decline",
        "social.friends.remove",
    ):
        assert check_mutation(DEFAULT_POLICY, action) == "network_disabled"
        assert check_mutation(Policy(network_enabled=True), action) == "ok"


def test_live_client_friend_paths_use_v1_friends() -> None:
    seen: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        seen.append((request.method, request.url.path, body))
        return httpx.Response(200, json={"friend": {"target_id": "Rival"}})

    client = _make_live_client(handler, ONLINE)

    client.friends("list")
    client.friends("add", target_id="Rival", idempotency_key="w14-live-add")
    client.friends("accept", target_id="Rival", idempotency_key="w14-live-accept")
    client.friends("decline", target_id="Rival", idempotency_key="w14-live-decline")
    client.friends("remove", target_id="Rival", idempotency_key="w14-live-remove")

    assert seen[0][0:2] == ("GET", "/v1/friends")
    assert seen[1][0:2] == ("POST", "/v1/friends")
    assert seen[1][2]["target_id"] == "Rival"
    assert seen[2][0:2] == ("POST", "/v1/friends/Rival/accept")
    assert seen[3][0:2] == ("POST", "/v1/friends/Rival/decline")
    assert seen[4][0:2] == ("DELETE", "/v1/friends/Rival")


def test_live_client_history_path_uses_v1_social_history() -> None:
    seen: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                request.method,
                request.url.path,
                dict(request.url.params),
            )
        )
        return httpx.Response(200, json={"items": [], "count": 0})

    client = _make_live_client(handler, ONLINE)

    assert client.social_history(filter="mentions")["count"] == 0
    assert client.history(filter="taunts_sent")["count"] == 0

    assert seen[0] == ("GET", "/v1/social/history", {"filter": "mentions"})
    assert seen[1] == ("GET", "/v1/social/history", {"filter": "taunts_sent"})


def test_social_api_friend_and_history_wrappers_delegate() -> None:
    calls: list[str] = []

    class Stub:
        def friends(self, action="list", *, target_id=None, idempotency_key=None):
            calls.append(f"friends:{action}:{target_id}")
            return {"status": action}

        def social_history(self, *, filter="all"):
            calls.append(f"history:{filter}")
            return {"filter": filter}

    api = SocialAPI(Stub())

    assert list_friends(api.client) == {"status": "list"}
    assert add_friend(api.client, "Rival") == {"status": "add"}
    assert remove_friend(api.client, "Rival") == {"status": "remove"}
    assert social_history(api.client, filter="mentions") == {"filter": "mentions"}

    assert calls == [
        "friends:list:None",
        "friends:add:Rival",
        "friends:remove:Rival",
        "history:mentions",
    ]
