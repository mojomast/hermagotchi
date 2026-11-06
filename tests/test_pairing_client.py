"""Device-pairing client and session-store tests (HGT-W7-Q)."""

from __future__ import annotations

import json
import logging
import os
import stat
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_client.auth import PairingClient, SessionStore, normalise_user_code  # noqa: E402
from game_client.client import GameClient  # noqa: E402
from game_client.errors import GameClientError  # noqa: E402
import schemas  # noqa: E402
import tools  # noqa: E402

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


def make_store(tmp_path: Path, **kwargs) -> SessionStore:
    return SessionStore(
        environ={"HERMES_PLUGIN_DATA_DIR": str(tmp_path / "plugins_data")},
        **kwargs,
    )


def make_pair_client(handler, store: SessionStore, **kwargs) -> PairingClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return PairingClient(
        "http://testserver/v1",
        store=store,
        http_client=http_client,
        **kwargs,
    )


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_session_store_creates_private_dir_and_atomic_file(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    assert store.path == tmp_path / "plugins_data" / "hermagotchi" / "session.json"
    assert store.load() is None

    store.save(token_payload())
    assert json.loads(store.path.read_text(encoding="utf-8"))["access_token"] == ACCESS
    assert store.load()["refresh_token"] == REFRESH
    assert not list(store.path.parent.glob(".*.tmp"))

    store.save(token_payload(access_token=NEXT_ACCESS, refresh_token=NEXT_REFRESH))
    assert store.load()["access_token"] == NEXT_ACCESS
    assert not list(store.path.parent.glob(".*.tmp"))

    if os.name != "nt":
        assert _mode(store.path.parent) == 0o700
        assert _mode(store.path) == 0o600


def test_session_store_clear_removes_file(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())

    store.clear()

    assert store.load() is None
    assert not store.path.exists()
    store.clear()


def test_session_store_repr_and_errors_never_expose_tokens(tmp_path: Path, caplog) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())

    with caplog.at_level(logging.DEBUG):
        logging.getLogger("game_client.auth").debug("store=%r", store)

    assert ACCESS not in repr(store)
    assert REFRESH not in repr(store)
    assert ACCESS not in caplog.text
    assert REFRESH not in caplog.text

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "code": "invalid_grant",
                "message": f"bad token {REFRESH}",
                "retry_after_s": 0,
                "correlation_id": "corr_1",
                "access_token": ACCESS,
                "refresh_token": REFRESH,
            },
        )

    client = make_pair_client(handler, store)
    with pytest.raises(GameClientError) as excinfo:
        client.list_devices()

    rendered = f"{excinfo.value}{excinfo.value.as_dict()}{excinfo.value.payload}"
    assert ACCESS not in rendered
    assert REFRESH not in rendered


def test_start_pending_then_token_saves_session(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        assert "authorization" not in request.headers
        if request.url.path == "/v1/auth/pair/start":
            body = json.loads(request.content)
            assert body == {
                "device_name": "Desktop",
                "new_account": True,
                "public_handle": "ada",
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
            if len(calls) == 2:
                return httpx.Response(
                    400,
                    json={
                        "code": "authorization_pending",
                        "message": "Waiting for approval.",
                        "retry_after_s": 5,
                        "correlation_id": "corr_pending",
                    },
                )
            return httpx.Response(200, json=token_payload())
        raise AssertionError(request.url.path)

    client = make_pair_client(handler, store)
    started = client.start("Desktop", new_account=True, public_handle="ada")

    assert started["user_code"] == "BCDF-GHJK"
    with pytest.raises(GameClientError) as pending:
        client.poll_token(DEVICE_CODE)
    assert pending.value.code == "authorization_pending"
    assert pending.value.retry_after_s == 5

    tokens = client.poll_token(started["device_code"])
    assert tokens["account_id"] == "acct_1"
    assert store.load()["access_token"] == ACCESS
    assert store.load()["refresh_token"] == REFRESH
    assert calls == [
        ("POST", "/v1/auth/pair/start"),
        ("POST", "/v1/auth/pair/token"),
        ("POST", "/v1/auth/pair/token"),
    ]


def test_approve_normalises_user_code_and_uses_bearer(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"approved": True, "device_name": "Laptop"}
        )

    client = make_pair_client(handler, store)
    result = client.approve(" bcdf - ghjk ")

    assert result == {"approved": True, "device_name": "Laptop"}
    assert seen["path"] == "/v1/auth/pair/approve"
    assert seen["auth"] == f"Bearer {ACCESS}"
    assert seen["body"] == {"user_code": "BCDFGHJK"}


def test_refresh_rotates_and_saves_both_tokens(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "path": request.url.path,
                "auth": request.headers.get("Authorization"),
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(
            200,
            json=token_payload(
                access_token=NEXT_ACCESS, refresh_token=NEXT_REFRESH
            ),
        )

    client = make_pair_client(handler, store)
    result = client.refresh()

    assert result["access_token"] == NEXT_ACCESS
    assert seen == [
        {
            "path": "/v1/auth/refresh",
            "auth": None,
            "body": {"refresh_token": REFRESH},
        }
    ]
    assert store.load()["access_token"] == NEXT_ACCESS
    assert store.load()["refresh_token"] == NEXT_REFRESH


def test_refresh_reuse_invalid_grant_clears_local_session(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "code": "invalid_grant",
                "message": "Refresh token reused.",
                "retry_after_s": 0,
                "correlation_id": "corr_reuse",
            },
        )

    client = make_pair_client(handler, store)
    with pytest.raises(GameClientError) as excinfo:
        client.refresh()

    assert excinfo.value.code == "invalid_grant"
    assert store.load() is None


def test_list_devices_refreshes_once_on_401(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (request.url.path, request.headers.get("Authorization"))
        )
        if request.url.path == "/v1/auth/devices":
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
            return httpx.Response(
                200,
                json={
                    "devices": [
                        {
                            "device_id": "dev_1",
                            "device_name": "Desktop",
                            "created_at": "2026-11-06T00:00:00Z",
                            "last_seen_at": "2026-11-06T00:00:00Z",
                            "current": True,
                            "revoked": False,
                        }
                    ]
                },
            )
        if request.url.path == "/v1/auth/refresh":
            return httpx.Response(
                200,
                json=token_payload(
                    access_token=NEXT_ACCESS, refresh_token=NEXT_REFRESH
                ),
            )
        raise AssertionError(request.url.path)

    client = make_pair_client(handler, store)
    result = client.list_devices()

    assert result["devices"][0]["device_id"] == "dev_1"
    assert seen == [
        ("/v1/auth/devices", f"Bearer {ACCESS}"),
        ("/v1/auth/refresh", None),
        ("/v1/auth/devices", f"Bearer {NEXT_ACCESS}"),
    ]
    assert store.load()["refresh_token"] == NEXT_REFRESH


def test_revoke_current_device_clears_local_session(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"revoked": True})

    client = make_pair_client(handler, store)
    assert client.revoke("dev_1") == {"revoked": True}

    assert seen["path"] == "/v1/auth/devices/dev_1/revoke"
    assert seen["auth"] == f"Bearer {ACCESS}"
    assert store.load() is None


def test_revoke_other_device_keeps_local_session(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(token_payload())

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"revoked": True})

    client = make_pair_client(handler, store)
    client.revoke("dev_other")

    assert store.load()["device_id"] == "dev_1"


def test_game_client_token_provider_sends_bearer_without_account_header() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["account"] = request.headers.get("X-Account-Id")
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = GameClient(
        "http://testserver/v1",
        http_client=http_client,
        headers={"X-Account-Id": "stub-account"},
        token_provider=lambda: ACCESS,
        max_retries=0,
        sleep=lambda _seconds: None,
    )

    assert client.health()["status"] == "ok"
    assert seen["auth"] == f"Bearer {ACCESS}"
    assert seen["account"] is None


def test_game_client_falls_back_to_account_header_without_session() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["account"] = request.headers.get("X-Account-Id")
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = GameClient(
        "http://testserver/v1",
        http_client=http_client,
        headers={"X-Account-Id": "stub-account"},
        token_provider=lambda: None,
        max_retries=0,
        sleep=lambda _seconds: None,
    )

    client.health()
    assert seen["auth"] is None
    assert seen["account"] == "stub-account"


def test_fake_pair_flow_returns_only_safe_session_fields() -> None:
    client = tools.FakeGameClient(policy={"network_enabled": True})

    started = client.execute(
        "hermagotchi_status",
        {"op": "pair", "device_name": "Desktop", "new_account": True},
    )
    assert started["ok"] is True, started
    assert normalise_user_code(started["data"]["user_code"]) == started["data"][
        "user_code"
    ].replace("-", "")
    assert started["data"]["paired"] is False
    assert started["data"]["account_id"] is None

    paired = client.execute("hermagotchi_status", {"op": "pair"})
    assert paired["ok"] is True, paired
    assert paired["data"]["paired"] is True
    assert paired["data"]["account_id"]
    assert paired["data"]["devices"]

    current = next(row for row in paired["data"]["devices"] if row["current"])
    revoked = client.execute(
        "hermagotchi_status",
        {
            "op": "pair",
            "revoke_device_id": current["device_id"],
            "idempotency_key": "pair-revoke-1",
        },
    )
    assert revoked["ok"] is True, revoked
    assert revoked["data"]["revoked"] is True
    assert revoked["data"]["paired"] is False

    for reply in (started, paired, revoked):
        rendered = json.dumps(reply)
        assert "access_token" not in rendered
        assert "refresh_token" not in rendered
        assert "device_code" not in rendered


def test_fake_pair_approve_is_mutating() -> None:
    client = tools.FakeGameClient(policy={"network_enabled": True})
    assert client.policy["agent_autonomy_enabled"] is False
    started = client.execute(
        "hermagotchi_status",
        {"op": "pair", "device_name": "Desktop", "new_account": True},
    )
    assert started["ok"] is True
    paired = client.execute("hermagotchi_status", {"op": "pair"})
    assert paired["ok"] is True

    client.pending_pairing = {
        "user_code": "BCDFGHJK",
        "device_name": "Laptop",
        "approved": False,
        "used": False,
        "created_at": tools._now(),
    }

    missing_key = client.execute(
        "hermagotchi_status", {"op": "pair", "user_code": "BCDF-GHJK"}
    )
    assert missing_key["ok"] is False
    assert missing_key["error_code"] == "missing_idempotency_key"

    approved = client.execute(
        "hermagotchi_status",
        {
            "op": "pair",
            "user_code": "bcdf-ghjk",
            "idempotency_key": "pair-approve-1",
        },
    )
    assert approved["ok"] is True, approved
    assert approved["data"] == {"approved": True, "device_name": "Laptop"}

    offline = tools.FakeGameClient()
    blocked = offline.execute(
        "hermagotchi_status",
        {
            "op": "pair",
            "revoke_device_id": "dev_1",
            "idempotency_key": "pair-revoke-offline",
        },
    )
    assert blocked["ok"] is False
    assert blocked["error_code"] == "network_disabled"


def test_status_schema_exposes_pair_and_keeps_eight_tools() -> None:
    schema = schemas.TOOL_SCHEMAS["hermagotchi_status"]
    assert "pair" in schema["properties"]["op"]["enum"]
    props = schema["properties"]
    assert props["user_code"]["type"] == "string"
    assert props["user_code"]["maxLength"] == 9
    assert props["device_name"]["maxLength"] == 64
    assert props["new_account"]["type"] == "boolean"
    assert props["revoke_device_id"]["type"] == "string"

    assert len(schemas.TOOL_SCHEMAS) == 8
    assert set(schemas.TOOL_SCHEMAS) == set(schemas.TOOL_NAMES)
    assert len(tools.HANDLERS) == 8
