"""Unit tests for the local dashboard bridge (HGT-W3-H)."""

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
from game_client import GameClient, GameClientError, PolicyGate  # noqa: E402


class FakeClient:
    def __init__(self, *, network_enabled=True, error=None):
        self.policy = PolicyGate({"network_enabled": network_enabled})
        self.error = error
        self.calls: list[str] = []

    def health(self):
        self.calls.append("health")
        if self.error is not None:
            raise self.error
        return {"status": "ok", "service": "hermagotchi"}

    def me(self):
        self.calls.append("me")
        if self.error is not None:
            raise self.error
        return {"account": {"id": "acct_1"}, "policy": {"mode": "human"}}

    def status(self):
        self.calls.append("status")
        if self.error is not None:
            raise self.error
        return {
            "health": {"status": "ok"},
            "me": {"account": {"id": "acct_1"}},
            "policy": self.policy.as_dict(),
        }


def build_app(fake):
    app = FastAPI()
    app.include_router(
        plugin_api.create_router(client_factory=lambda: fake),
        prefix="/api/plugins/hermagotchi",
    )
    return app


def test_manifest_names_the_plugin_and_api_file():
    manifest = json.loads(
        (ROOT / "dashboard" / "manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["name"] == "hermagotchi"
    assert manifest["api"] == "plugin_api.py"
    assert manifest["entry"] == "dist/index.js"
    assert manifest["tab"]["path"] == "/hermagotchi"


def test_module_exports_apirouter_with_health_and_status():
    from fastapi import APIRouter

    assert isinstance(plugin_api.router, APIRouter)
    paths = {route.path for route in plugin_api.router.routes}
    assert "/health" in paths
    assert "/status" in paths


def test_health_proxies_the_game_client():
    fake = FakeClient()
    client = TestClient(build_app(fake))

    response = client.get("/api/plugins/hermagotchi/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "ok"
    assert body["health"] == {"status": "ok", "service": "hermagotchi"}
    assert body["policy"]["network_enabled"] is True
    assert fake.calls == ["health"]


def test_status_reads_health_and_me_through_the_client():
    fake = FakeClient()
    client = TestClient(build_app(fake))

    response = client.get("/api/plugins/hermagotchi/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "ok"
    assert body["health"]["status"] == "ok"
    assert body["me"]["account"]["id"] == "acct_1"
    assert body["policy"]["network_enabled"] is True
    assert fake.calls == ["status"]


def test_status_composes_health_and_me_when_client_has_no_status_method():
    class ReadOnlyClient:
        policy = PolicyGate({"network_enabled": True})

        def __init__(self):
            self.calls = []

        def health(self):
            self.calls.append("health")
            return {"status": "ok"}

        def me(self):
            self.calls.append("me")
            return {"account": {"id": "acct_2"}}

    fake = ReadOnlyClient()
    client = TestClient(build_app(fake))

    response = client.get("/api/plugins/hermagotchi/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["me"]["account"]["id"] == "acct_2"
    assert fake.calls == ["health", "me"]


def test_status_endpoint_uses_module_router_dependency_override():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/healthz":
            return httpx.Response(200, json={"status": "ok", "service": "hermagotchi"})
        if request.url.path == "/v1/me":
            return httpx.Response(
                200,
                json={
                    "account": {"id": "acct_3"},
                    "policy": {
                        "mode": "human",
                        "network_enabled": True,
                        "autonomy_enabled": False,
                        "chat_enabled": False,
                    },
                },
            )
        raise AssertionError(f"unexpected path {request.url.path}")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    game_client = GameClient(
        base_url="https://testserver/v1",
        policy={"network_enabled": True},
        http_client=http_client,
        max_retries=0,
        sleep=lambda _seconds: None,
    )

    app = FastAPI()
    app.include_router(plugin_api.router, prefix="/api/plugins/hermagotchi")
    app.dependency_overrides[plugin_api.get_client] = lambda: game_client
    client = TestClient(app)

    health = client.get("/api/plugins/hermagotchi/health")
    status = client.get("/api/plugins/hermagotchi/status")

    assert health.status_code == 200
    assert health.json()["health"]["status"] == "ok"
    assert status.status_code == 200
    body = status.json()
    assert body["me"]["account"]["id"] == "acct_3"
    assert body["policy"]["network_enabled"] is True


@pytest.mark.parametrize(
    "code, expected_status",
    [
        ("network_disabled", "offline"),
        ("network_error", "offline"),
        ("unauthorized", "unauthorized"),
        ("expired", "expired"),
        ("unavailable", "unavailable"),
    ],
)
def test_health_maps_client_errors_to_coherent_states(code, expected_status):
    error = GameClientError(
        code=code,
        message="bridge unavailable",
        status_code=503,
        retry_after_s=2,
        correlation_id="corr_9",
    )
    client = TestClient(build_app(FakeClient(error=error)))

    response = client.get("/api/plugins/hermagotchi/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == expected_status
    assert body["error"] == {
        "code": code,
        "message": "bridge unavailable",
        "retry_after_s": 2,
        "correlation_id": "corr_9",
    }


def test_offline_status_keeps_policy_and_does_not_leak_details():
    error = GameClientError(
        code="network_disabled",
        message="Network is disabled.",
        status_code=403,
        correlation_id="corr_10",
    )
    client = TestClient(build_app(FakeClient(error=error)))

    response = client.get("/api/plugins/hermagotchi/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "offline"
    assert body["policy"]["network_enabled"] is True
    assert set(body["error"]) == {
        "code",
        "message",
        "retry_after_s",
        "correlation_id",
    }


def test_dashboard_module_has_no_credential_globals():
    forbidden = {
        "api_key",
        "api_token",
        "authorization",
        "password",
        "secret",
        "token",
    }

    assert not (forbidden & {name.lower() for name in dir(plugin_api)})
