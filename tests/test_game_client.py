"""Unit tests for the Hermagotchi hosted API client (HGT-W3-H)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_client import (  # noqa: E402
    DEFAULT_POLICY,
    GameClient,
    GameClientError,
    PolicyDeniedError,
    PolicyGate,
    idempotency_key,
    new_idempotency_key,
)


def make_client(handler, *, policy=None, max_retries=0, sleep=None, **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://testserver")
    return GameClient(
        base_url="https://testserver/v1",
        policy=policy,
        http_client=http_client,
        max_retries=max_retries,
        sleep=sleep or (lambda _seconds: None),
        **kwargs,
    )


def test_default_policy_matches_contract_defaults():
    gate = PolicyGate()

    assert DEFAULT_POLICY["mode"] == "human"
    assert gate.mode == "human"
    assert gate.network_enabled is False
    assert gate.autonomy_enabled is False
    assert gate.chat_enabled is False
    assert gate.as_dict() == {
        "mode": "human",
        "network_enabled": False,
        "autonomy_enabled": False,
        "chat_enabled": False,
    }


def test_policy_accepts_agent_prefixed_aliases():
    gate = PolicyGate(
        {
            "mode": "agent",
            "network_enabled": True,
            "agent_autonomy_enabled": True,
            "agent_chat_enabled": True,
        }
    )

    assert gate.mode == "agent"
    assert gate.network_enabled is True
    assert gate.autonomy_enabled is True
    assert gate.chat_enabled is True


def test_policy_string_false_does_not_enable_network():
    gate = PolicyGate({"network_enabled": "false"})

    assert gate.network_enabled is False


def test_mutation_blocked_without_network_makes_no_request():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(201, json={"id": "pet_1"})

    client = make_client(handler)

    with pytest.raises(PolicyDeniedError) as excinfo:
        client.adopt_pet("byteblob", name="Nib")

    assert excinfo.value.code == "network_disabled"
    assert calls == []


def test_autonomy_gate_blocks_agent_actions_by_default():
    gate = PolicyGate({"network_enabled": True})

    with pytest.raises(PolicyDeniedError) as excinfo:
        gate.require_autonomy("battle.practice")

    assert excinfo.value.code == "autonomy_disabled"


def test_network_enabled_mutation_sends_idempotency_header_and_body():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["header"] = request.headers.get("Idempotency-Key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={"contracts_version": "contracts-v1", "id": "pet_1", "name": "Nib"},
        )

    client = make_client(handler, policy={"network_enabled": True})
    result = client.adopt_pet("byteblob", name="Nib", idempotency_key="idem-123")

    assert result["id"] == "pet_1"
    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/pets"
    assert seen["header"] == "idem-123"
    assert seen["body"]["idempotency_key"] == "idem-123"
    assert seen["body"]["species"] == "byteblob"


def test_mutation_generates_idempotency_key_when_omitted():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["header"] = request.headers.get("Idempotency-Key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "pet_1"})

    client = make_client(handler, policy={"network_enabled": True})
    client.adopt_pet("byteblob")

    assert isinstance(seen["header"], str) and len(seen["header"]) >= 16
    assert seen["body"]["idempotency_key"] == seen["header"]


def test_chat_mutation_blocked_when_chat_disabled():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={})

    client = make_client(
        handler, policy={"network_enabled": True, "chat_enabled": False}
    )

    with pytest.raises(PolicyDeniedError) as excinfo:
        client.send_message("channel_1", "hello")

    assert excinfo.value.code == "chat_disabled"
    assert calls == []


def test_chat_mutation_allowed_when_chat_enabled():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"message_id": "msg_1"})

    client = make_client(
        handler, policy={"network_enabled": True, "chat_enabled": True}
    )
    result = client.send_message("channel_1", "hello")

    assert result["message_id"] == "msg_1"
    assert seen["path"] == "/v1/chat/channels/channel_1/messages"
    assert seen["body"]["body"] == "hello"


def test_idempotency_key_helpers_return_unique_values():
    first = idempotency_key()
    second = idempotency_key()
    third = new_idempotency_key()

    assert isinstance(first, str) and first
    assert len({first, second, third}) == 3


def test_get_requests_retry_with_backoff():
    calls: list[str] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(
                503,
                headers={"Retry-After": "0"},
                json={
                    "code": "unavailable",
                    "message": "warming up",
                    "retry_after_s": 0,
                    "correlation_id": "corr_1",
                },
            )
        return httpx.Response(200, json={"status": "ok", "service": "hermagotchi"})

    client = make_client(handler, max_retries=1, sleep=sleeps.append)
    result = client.health()

    assert result["status"] == "ok"
    assert len(calls) == 2
    assert sleeps == [0.0]


def test_mutations_are_never_retried():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
            503,
            json={
                "code": "unavailable",
                "message": "try later",
                "retry_after_s": 5,
                "correlation_id": "corr_2",
            },
        )

    client = make_client(
        handler, policy={"network_enabled": True}, max_retries=3
    )

    with pytest.raises(GameClientError) as excinfo:
        client.purchase("hat.binary_crown", idempotency_key="idem-9")

    assert excinfo.value.status_code == 503
    assert excinfo.value.code == "unavailable"
    assert excinfo.value.retry_after_s == 5
    assert excinfo.value.correlation_id == "corr_2"
    assert len(calls) == 1


def test_transport_errors_retry_only_for_get_requests():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        raise httpx.ConnectError("offline", request=request)

    client = make_client(handler, max_retries=2)
    with pytest.raises(GameClientError) as excinfo:
        client.health()

    assert excinfo.value.code == "network_error"
    assert len(calls) == 3

    calls.clear()
    mutating = make_client(
        handler, policy={"network_enabled": True}, max_retries=2
    )
    with pytest.raises(GameClientError):
        mutating.purchase("aura.glitch_spark")
    assert len(calls) == 1


def test_read_routes_use_contract_paths_and_return_json():
    responses = {
        ("GET", "/v1/healthz"): {"status": "ok"},
        ("GET", "/v1/me"): {"account": {"id": "acct_1"}},
        ("GET", "/v1/pets/pet_1"): {"id": "pet_1"},
        ("GET", "/v1/matches/match_1"): {"match": {"match_id": "match_1"}},
        ("GET", "/v1/wallet"): {"balance": 42},
        ("GET", "/v1/ledger"): {"entries": []},
        ("GET", "/v1/catalog"): {"items": []},
        ("GET", "/v1/bounties"): {"bounties": []},
        ("GET", "/v1/leaderboard"): {"entries": []},
    }
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.method} {request.url.path}")
        return httpx.Response(200, json=responses[(request.method, request.url.path)])

    client = make_client(handler, policy={"network_enabled": True})

    assert client.health()["status"] == "ok"
    assert client.me()["account"]["id"] == "acct_1"
    assert client.get_pet("pet_1")["id"] == "pet_1"
    assert client.get_match("match_1")["match"]["match_id"] == "match_1"
    assert client.wallet()["balance"] == 42
    assert client.ledger(limit=5, offset=10)["entries"] == []
    assert client.catalog()["items"] == []
    assert client.list_bounties()["bounties"] == []
    assert client.leaderboard()["entries"] == []

    assert seen == [
        "GET /v1/healthz",
        "GET /v1/me",
        "GET /v1/pets/pet_1",
        "GET /v1/matches/match_1",
        "GET /v1/wallet",
        "GET /v1/ledger",
        "GET /v1/catalog",
        "GET /v1/bounties",
        "GET /v1/leaderboard",
    ]


def test_ledger_sends_pagination_query_parameters():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["query"] = request.url.query.decode()
        return httpx.Response(200, json={"entries": []})

    client = make_client(handler, policy={"network_enabled": True})
    client.ledger(limit=7, offset=21)

    assert seen["query"] == "limit=7&offset=21"


def test_error_envelope_is_parsed_into_exception_attributes():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "code": "conflict",
                "message": "Already adopted.",
                "retry_after_s": 0,
                "correlation_id": "corr_3",
            },
        )

    client = make_client(handler)

    with pytest.raises(GameClientError) as excinfo:
        client.get_pet("pet_1")

    error = excinfo.value
    assert error.status_code == 409
    assert error.code == "conflict"
    assert error.message == "Already adopted."
    assert error.retry_after_s == 0
    assert error.correlation_id == "corr_3"
    assert error.as_dict() == {
        "code": "conflict",
        "message": "Already adopted.",
        "retry_after_s": 0,
        "correlation_id": "corr_3",
    }


def test_status_combines_health_me_and_policy():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/healthz":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/v1/me":
            return httpx.Response(200, json={"account": {"id": "acct_1"}})
        raise AssertionError(f"unexpected path {request.url.path}")

    client = make_client(handler, policy={"network_enabled": True})
    result = client.status()

    assert result["health"]["status"] == "ok"
    assert result["me"]["account"]["id"] == "acct_1"
    assert result["policy"]["network_enabled"] is True


def test_base_url_gets_v1_suffix_once():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = GameClient(
        base_url="https://testserver",
        http_client=http_client,
        max_retries=0,
        sleep=lambda _seconds: None,
    )

    client.health()
    assert seen["path"] == "/v1/healthz"
