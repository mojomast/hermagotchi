"""Bridge endpoint tests for HGT-W8-R (no live network)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard import plugin_api  # noqa: E402
from game_client.auth import PairingClient, SessionStore  # noqa: E402

PREFIX = "/api/plugins/hermagotchi"
ACCESS = "hga_" + "a" * 32
REFRESH = "hgr_" + "r" * 32
NEXT_ACCESS = "hga_" + "b" * 32
NEXT_REFRESH = "hgr_" + "s" * 32
DEVICE_CODE = "hgd_" + "d" * 32


def token_payload(**overrides):
    payload = {
        "access_token": ACCESS,
        "refresh_token": REFRESH,
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_expires_in": 2592000,
        "account_id": "acct_1",
        "device_id": "dev_1",
    }
    payload.update(overrides)
    return payload


def make_store(tmp_path: Path) -> SessionStore:
    return SessionStore(
        tmp_path / "plugins_data" / "hermagotchi" / "session.json"
    )


def make_pair_client(handler, store: SessionStore) -> PairingClient:
    return PairingClient(
        "http://testserver/v1",
        store=store,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def build_app(pair_client, store: SessionStore) -> FastAPI:
    app = FastAPI()
    app.include_router(
        plugin_api.create_router(
            pairing_client_factory=lambda: pair_client,
            session_store=store,
        ),
        prefix=PREFIX,
    )
    return app


def test_unknown_proxy_path_is_rejected_without_network(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())
    called: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request.url.path)
        raise AssertionError("server must not be called for a rejected path")

    client = TestClient(build_app(make_pair_client(handler, store), store))
    response = client.get(f"{PREFIX}/proxy/v1/admin/secret")

    assert response.status_code == 404
    body = response.json()
    assert body == {
        "ok": False,
        "status": "not_allowed",
        "error": {
            "code": "not_allowed",
            "message": "That bridge path is not allowlisted.",
            "retry_after_s": 0,
        },
    }
    assert called == []


@pytest.mark.parametrize(
    "path",
    [
        "me",
        "wallet",
        "ledger",
        "catalog",
        "pets",
        "pets/pet_1",
        "pets/pet_1/equip",
        "pets/pet_1/unequip",
        "pets/pet_1/care",
        "goals",
        "goals/clear",
        "shop/purchases",
        "challenges",
        "challenges/ch_1/respond",
        "challenges/inbox",
        "practice",
        "matches/m_1",
        "matches/m_1/tactics",
        "leaderboard",
        "bounties",
        "bounties/b_1/claim",
        "chat/channels/lobby/messages",
        "moderation/report",
        "blocks",
        "blocks/block_1",
        "healthz",
    ],
)
def test_allowlist_accepts_every_contract_route(path: str) -> None:
    assert plugin_api._match_proxy_path(path) == path


def test_bearer_is_added_server_side_and_absent_from_response(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        seen["account"] = request.headers.get("X-Account-Id")
        return httpx.Response(200, json={"balance": 25, "revision": 2})

    client = TestClient(build_app(make_pair_client(handler, store), store))
    response = client.get(f"{PREFIX}/proxy/v1/wallet")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "ok"
    assert body["data"] == {"balance": 25, "revision": 2}
    assert seen == {
        "path": "/v1/wallet",
        "auth": f"Bearer {ACCESS}",
        "account": None,
    }
    assert ACCESS not in response.text
    assert REFRESH not in response.text


def test_missing_session_returns_auth_missing_without_calling_server(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    called: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request.url.path)
        raise AssertionError("server must not be called without a session")

    client = TestClient(build_app(make_pair_client(handler, store), store))
    response = client.get(f"{PREFIX}/proxy/v1/wallet")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "auth_missing"
    assert body["error"]["code"] == "auth_missing"
    assert called == []


def test_proxy_refreshes_once_on_401_then_retries(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers.get("Authorization")))
        if request.url.path == "/v1/wallet":
            if request.headers.get("Authorization") == f"Bearer {ACCESS}":
                return httpx.Response(
                    401,
                    json={
                        "code": "expired_token",
                        "message": "Access token expired.",
                        "retry_after_s": 0,
                        "correlation_id": "corr_expired",
                    },
                )
            return httpx.Response(200, json={"balance": 41})
        if request.url.path == "/v1/auth/refresh":
            assert json.loads(request.content) == {"refresh_token": REFRESH}
            return httpx.Response(
                200,
                json=token_payload(
                    access_token=NEXT_ACCESS, refresh_token=NEXT_REFRESH
                ),
            )
        raise AssertionError(request.url.path)

    client = TestClient(build_app(make_pair_client(handler, store), store))
    response = client.get(f"{PREFIX}/proxy/v1/wallet")

    assert response.json()["ok"] is True
    assert response.json()["data"] == {"balance": 41}
    assert seen == [
        ("/v1/wallet", f"Bearer {ACCESS}"),
        ("/v1/auth/refresh", None),
        ("/v1/wallet", f"Bearer {NEXT_ACCESS}"),
    ]
    assert store.load()["access_token"] == NEXT_ACCESS
    assert NEXT_ACCESS not in response.text
    assert NEXT_REFRESH not in response.text


def test_401_after_refresh_is_reported_as_unauthorized_without_looping(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1/auth/refresh":
            return httpx.Response(
                200,
                json=token_payload(
                    access_token=NEXT_ACCESS, refresh_token=NEXT_REFRESH
                ),
            )
        return httpx.Response(
            401,
            json={
                "code": "unauthorized",
                "message": "A valid account session is required.",
                "retry_after_s": 0,
            },
        )

    client = TestClient(build_app(make_pair_client(handler, store), store))
    response = client.get(f"{PREFIX}/proxy/v1/wallet")

    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "unauthorized"
    assert seen == ["/v1/wallet", "/v1/auth/refresh", "/v1/wallet"]


def test_network_failure_maps_to_offline(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("service down", request=request)

    client = TestClient(build_app(make_pair_client(handler, store), store))
    response = client.get(f"{PREFIX}/proxy/v1/wallet")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "offline"
    assert body["error"]["code"] == "network_error"
    assert body["error"]["retry_after_s"] == 0


def test_proxy_never_returns_tokens_from_server_data(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "balance": 1,
                "access_token": ACCESS,
                "nested": {
                    "refresh_token": REFRESH,
                    "device_code": DEVICE_CODE,
                    "note": f"leaked {ACCESS}",
                },
            },
        )

    client = TestClient(build_app(make_pair_client(handler, store), store))
    response = client.get(f"{PREFIX}/proxy/v1/wallet")

    assert response.json()["data"]["balance"] == 1
    for secret in (ACCESS, REFRESH, DEVICE_CODE):
        assert secret not in response.text


def test_mutations_forward_json_and_idempotency_key(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("Idempotency-Key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"purchased": True})

    client = TestClient(build_app(make_pair_client(handler, store), store))
    response = client.post(
        f"{PREFIX}/proxy/v1/shop/purchases",
        json={"item_id": "item.crown"},
        headers={"Idempotency-Key": "idem-1"},
    )

    assert response.json()["data"] == {"purchased": True}
    assert seen == {
        "method": "POST",
        "path": "/v1/shop/purchases",
        "key": "idem-1",
        "body": {"item_id": "item.crown"},
    }


def test_mutations_generate_an_idempotency_key_when_absent(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get("Idempotency-Key")
        return httpx.Response(200, json={"ok": True})

    client = TestClient(build_app(make_pair_client(handler, store), store))
    client.post(f"{PREFIX}/proxy/v1/goals/clear", json={})

    assert isinstance(seen["key"], str)
    assert len(seen["key"] or "") >= 8


def test_pair_start_hides_device_code_and_poll_returns_only_account(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/pair/start":
            assert json.loads(request.content) == {
                "device_name": "Desktop",
                "new_account": True,
            }
            return httpx.Response(
                201,
                json={
                    "device_code": DEVICE_CODE,
                    "user_code": "BCDF-GHJK",
                    "expires_at": "2026-11-06T00:10:00Z",
                    "interval_s": 5,
                    "new_account": True,
                },
            )
        if request.url.path == "/v1/auth/pair/token":
            assert json.loads(request.content) == {"device_code": DEVICE_CODE}
            return httpx.Response(200, json=token_payload())
        raise AssertionError(request.url.path)

    client = TestClient(build_app(make_pair_client(handler, store), store))
    started = client.post(
        f"{PREFIX}/pair/start",
        json={"device_name": "Desktop", "new_account": True},
    )

    start_body = started.json()
    assert start_body["ok"] is True
    assert start_body["data"]["user_code"] == "BCDF-GHJK"
    assert start_body["data"]["paired"] is False
    assert start_body["data"]["expires_at"] == "2026-11-06T00:10:00Z"
    assert start_body["user_code"] == "BCDF-GHJK"
    assert start_body["paired"] is False
    assert DEVICE_CODE not in started.text

    polled = client.post(f"{PREFIX}/pair/poll")
    poll_body = polled.json()
    assert poll_body["ok"] is True
    assert poll_body["data"] == {"paired": True, "account_id": "acct_1"}
    assert poll_body["paired"] is True
    assert poll_body["account_id"] == "acct_1"
    assert store.load()["access_token"] == ACCESS
    assert DEVICE_CODE not in polled.text
    assert ACCESS not in polled.text
    assert REFRESH not in polled.text


def test_pair_poll_reports_pending_without_leaking_codes(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/pair/start":
            return httpx.Response(
                201,
                json={
                    "device_code": DEVICE_CODE,
                    "user_code": "BCDF-GHJK",
                    "expires_at": "2026-11-06T00:10:00Z",
                    "interval_s": 5,
                },
            )
        return httpx.Response(
            400,
            json={
                "code": "authorization_pending",
                "message": "Waiting for approval.",
                "retry_after_s": 5,
                "correlation_id": "corr_pending",
            },
        )

    client = TestClient(build_app(make_pair_client(handler, store), store))
    client.post(
        f"{PREFIX}/pair/start",
        json={"device_name": "Desktop", "new_account": True},
    )
    response = client.post(f"{PREFIX}/pair/poll")

    body = response.json()
    assert body["ok"] is True
    assert body["data"]["paired"] is False
    assert body["data"]["status"] == "pending"
    assert body["data"]["retry_after_s"] == 5
    assert DEVICE_CODE not in response.text


def test_pair_poll_reports_expiry(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/pair/start":
            return httpx.Response(
                201,
                json={
                    "device_code": DEVICE_CODE,
                    "user_code": "BCDF-GHJK",
                    "expires_at": "2026-11-06T00:10:00Z",
                },
            )
        return httpx.Response(
            400,
            json={
                "code": "expired_token",
                "message": "That device code has expired.",
                "retry_after_s": 0,
            },
        )

    client = TestClient(build_app(make_pair_client(handler, store), store))
    client.post(
        f"{PREFIX}/pair/start",
        json={"device_name": "Desktop", "new_account": True},
    )
    response = client.post(f"{PREFIX}/pair/poll")

    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "expired"
    assert body["error"]["code"] == "expired_token"


def test_pair_admin_endpoints_require_and_use_the_session(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers.get("Authorization")))
        if request.url.path == "/v1/auth/pair/approve":
            return httpx.Response(200, json={"approved": True, "device_name": "Laptop"})
        if request.url.path == "/v1/auth/devices":
            return httpx.Response(
                200,
                json={
                    "devices": [
                        {
                            "device_id": "dev_1",
                            "device_name": "Desktop",
                            "current": True,
                            "revoked": False,
                        }
                    ]
                },
            )
        if request.url.path == "/v1/auth/devices/dev_2/revoke":
            return httpx.Response(200, json={"revoked": True})
        if request.url.path == "/v1/auth/logout":
            return httpx.Response(200, json={"revoked": True})
        raise AssertionError(request.url.path)

    client = TestClient(build_app(make_pair_client(handler, store), store))

    missing = client.get(f"{PREFIX}/pair/devices")
    assert missing.json()["status"] == "auth_missing"
    assert seen == []

    store.save(token_payload())
    approved = client.post(
        f"{PREFIX}/pair/approve", json={"user_code": "bcdf-ghjk"}
    )
    devices = client.get(f"{PREFIX}/pair/devices")
    revoked = client.post(f"{PREFIX}/pair/devices/dev_2/revoke")
    logged_out = client.post(f"{PREFIX}/pair/logout")

    assert approved.json()["data"] == {"approved": True, "device_name": "Laptop"}
    assert devices.json()["data"]["devices"][0]["device_id"] == "dev_1"
    assert revoked.json()["data"] == {"revoked": True}
    assert logged_out.json()["data"] == {"revoked": True}
    assert store.load() is None
    assert seen == [
        ("/v1/auth/pair/approve", f"Bearer {ACCESS}"),
        ("/v1/auth/devices", f"Bearer {ACCESS}"),
        ("/v1/auth/devices/dev_2/revoke", f"Bearer {ACCESS}"),
        ("/v1/auth/logout", f"Bearer {ACCESS}"),
    ]
