"""Local asset bridge tests (HGT-W9-V, no live network)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard import plugin_api  # noqa: E402
from game_client import PolicyGate  # noqa: E402

PREFIX = "/api/plugins/hermagotchi"


class FakeClient:
    policy = PolicyGate({"network_enabled": True})

    def status(self):
        return {
            "health": {"status": "ok"},
            "me": {"account": {"id": "acct_1"}},
        }

    def health(self):
        return {"status": "ok"}

    def me(self):
        return {"account": {"id": "acct_1"}}


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(
        plugin_api.create_router(client_factory=lambda: FakeClient()),
        prefix=PREFIX,
    )
    return app


def test_manifest_returns_the_best_on_disk_pack_as_raw_json() -> None:
    client = TestClient(build_app())

    response = client.get(f"{PREFIX}/assets/manifest")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body.get("asset_pack_id") == "launch-003"
    assert "species" in body
    assert "animations" in body
    assert "ok" not in body
    assert "data" not in body


def test_manifest_prefers_launch_003_then_falls_back(tmp_path: Path, monkeypatch) -> None:
    fallback = {"asset_pack_id": "launch-001", "species": {}, "assets": []}
    preferred = {"asset_pack_id": "launch-003", "species": {}, "assets": []}
    (tmp_path / "manifest.json").write_text(json.dumps(fallback), encoding="utf-8")
    monkeypatch.setattr(plugin_api, "_assets_dir", lambda: tmp_path)
    client = TestClient(build_app())

    first = client.get(f"{PREFIX}/assets/manifest")
    assert first.status_code == 200
    assert first.json()["asset_pack_id"] == "launch-001"

    (tmp_path / "manifest.launch-003.json").write_text(
        json.dumps(preferred), encoding="utf-8"
    )
    second = client.get(f"{PREFIX}/assets/manifest")
    assert second.status_code == 200
    assert second.json()["asset_pack_id"] == "launch-003"


def test_asset_files_are_served_from_the_plugin_assets_directory() -> None:
    client = TestClient(build_app())

    response = client.get(f"{PREFIX}/assets/px3/species/byteblob_body.png")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_missing_asset_returns_404() -> None:
    client = TestClient(build_app())

    response = client.get(f"{PREFIX}/assets/px3/species/not_a_real_pet.png")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "asset_not_found"


def test_asset_path_resolver_rejects_traversal_and_escapes() -> None:
    assert plugin_api._resolve_asset_path("../dashboard/plugin_api.py") is None
    assert plugin_api._resolve_asset_path("px3/../../dashboard/plugin_api.py") is None
    assert plugin_api._resolve_asset_path("/etc/passwd") is None
    assert plugin_api._resolve_asset_path("") is None
    assert plugin_api._resolve_asset_path("px3/species/byteblob_body.png") is not None


@pytest.mark.parametrize(
    "traversal",
    [
        "%2e%2e/dashboard/plugin_api.py",
        "..%2Fdashboard%2Fplugin_api.py",
        "px3/%2e%2e/%2e%2e/dashboard/plugin_api.py",
    ],
)
def test_asset_http_route_rejects_traversal(traversal: str) -> None:
    client = TestClient(build_app())

    response = client.get(f"{PREFIX}/assets/{traversal}")

    assert response.status_code == 404
    assert b"plugin_api" not in response.content


def test_status_advertises_the_relative_asset_suffix_without_tokens() -> None:
    client = TestClient(build_app())

    response = client.get(f"{PREFIX}/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["asset_base_path"] == "assets"
    assert "hga_" not in response.text
    assert "hgr_" not in response.text
