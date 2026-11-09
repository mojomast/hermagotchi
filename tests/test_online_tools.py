"""Online mode: the eight tools act on a real game server (in-process app)."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import online_client  # noqa: E402
import tools  # noqa: E402
from game_client.auth import PairingClient, SessionStore  # noqa: E402

BASE = "https://testserver/v1"


def key() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def server(tmp_path: Path):
    from server.app.main import create_app

    app = create_app(db_path=tmp_path / "game.db")
    with TestClient(app, base_url="https://testserver") as client:
        yield client


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "plugin-data" / "session.json")


def online(server, store, **policy) -> tools.OnlineGameClient:
    pair = PairingClient(base_url=BASE, store=store, http_client=server)
    return tools.OnlineGameClient(online_client.OnlineTransport(pair), policy=policy)


def pair_new_account(server, store) -> None:
    pair = PairingClient(base_url=BASE, store=store, http_client=server)
    started = pair.start("pytest", new_account=True)
    pair.poll_token(started["device_code"])


def test_unpaired_online_reports_auth_missing(server, store) -> None:
    client = online(server, store)
    health = client.execute("hermagotchi_status", {"op": "health"})
    assert health["ok"] is True
    assert health["data"]["backend"] == "online"
    assert health["data"]["paired"] is False
    me = client.execute("hermagotchi_status", {"op": "me"})
    assert me == {**me, "ok": False, "error_code": "auth_missing"}


def test_all_tools_work_online_and_state_persists(server, store) -> None:
    pair_new_account(server, store)
    c = online(server, store, agent_autonomy_enabled=True)

    health = c.execute("hermagotchi_status", {"op": "health"})["data"]
    assert health["backend"] == "online" and health["persistent"] is True
    assert health["simulation"] is None and health["network_enabled"] is True

    adopt = c.execute("hermagotchi_pet", {"op": "adopt", "species": "byteblob",
                                          "name": "Pytest", "idempotency_key": key()})
    assert adopt["ok"], adopt
    care = c.execute("hermagotchi_pet", {"op": "care", "action": "feed", "idempotency_key": key()})
    assert care["ok"], care
    for op in ("me", "pet", "wallet", "goal", "inbox"):
        assert c.execute("hermagotchi_status", {"op": op})["ok"], op
    assert c.execute("hermagotchi_goals", {"op": "list"})["ok"]
    assert c.execute("hermagotchi_challenge", {"op": "list_opponents"})["ok"]
    practice = c.execute("hermagotchi_battle", {"op": "practice", "idempotency_key": key()})
    assert practice["ok"], practice
    match_id = practice["data"]["match_id"]
    assert c.execute("hermagotchi_battle", {"op": "get", "match_id": match_id})["ok"]
    assert c.execute("hermagotchi_shop", {"op": "catalog"})["ok"]
    assert c.execute("hermagotchi_shop", {"op": "inventory"})["ok"]
    assert c.execute("hermagotchi_social", {"op": "read"})["ok"]
    assert c.execute("hermagotchi_social", {"op": "friends"})["ok"]
    assert c.execute("hermagotchi_social", {"op": "history"})["ok"]
    assert c.execute("hermagotchi_meta", {"op": "leaderboard"})["ok"]
    assert c.execute("hermagotchi_meta", {"op": "bounties"})["ok"]

    # Autonomy-gated actions stay blocked by default even online.
    locked = online(server, store).execute("hermagotchi_battle", {"op": "practice", "idempotency_key": key()})
    assert locked["error_code"] == "autonomy_disabled"
    # Agent chat stays off unless the owner enables it.
    sent = c.execute("hermagotchi_social", {"op": "send", "body": "hi", "idempotency_key": key()})
    assert sent["ok"] is False

    pet_id = c.execute("hermagotchi_status", {"op": "me"})["data"]["pet_id"]
    # "Restart": brand-new client objects, same session store + server DB.
    again = online(server, store)
    me = again.execute("hermagotchi_status", {"op": "me"})
    assert me["ok"] and me["data"]["pet_id"] == pet_id

    text = json.dumps([adopt, care, practice, me])
    assert "access_token" not in text and "refresh_token" not in text
    assert store.access_token not in text


def test_online_bad_ids_are_rejected_locally(server, store) -> None:
    pair_new_account(server, store)
    c = online(server, store)
    bad = c.execute("hermagotchi_battle", {"op": "get", "match_id": "../me"})
    assert bad["ok"] is False and bad["error_code"] == "invalid_arguments"


def test_mode_switch_defaults_offline(monkeypatch) -> None:
    online_client.install_settings_getter(None)
    monkeypatch.delenv(online_client.ENV_NETWORK_ENABLED, raising=False)
    assert isinstance(tools.get_default_client(), tools.FakeGameClient)
    assert not isinstance(tools.get_default_client(), tools.OnlineGameClient)
    data = json.loads(tools.HANDLERS["hermagotchi_status"]({"op": "health"}))["data"]
    assert data["backend"] == "offline_practice"


def test_mode_switch_setting_enables_online(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HERMES_PLUGIN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv(online_client.ENV_API_BASE_URL, "https://api.example.com/v1")
    online_client.install_settings_getter(
        lambda k, d=None: True if k == "network_enabled" else d
    )
    try:
        client = tools.get_default_client()
        assert isinstance(client, tools.OnlineGameClient)
        assert client.transport.pair.store.path == tmp_path / "hermagotchi" / "session.json"
    finally:
        online_client.install_settings_getter(None)
        tools._ONLINE_CLIENT = None


def test_online_refuses_plain_http_remote(monkeypatch) -> None:
    from game_client.errors import GameClientError

    monkeypatch.setenv(online_client.ENV_API_BASE_URL, "http://api.example.com/v1")
    with pytest.raises(GameClientError):
        online_client.OnlineTransport.from_environment()


def test_online_pair_approve_via_tool_is_unsupported(server, store, monkeypatch) -> None:
    """teknium1 catalog review: agent must not approve pairings online."""
    pair_new_account(server, store)
    c = online(server, store)
    called = {"approve": 0}

    def boom(code: str):
        called["approve"] += 1
        raise AssertionError(f"approve must not run online via tool ({code!r})")

    monkeypatch.setattr(c.transport.pair, "approve", boom)
    out = c.execute(
        "hermagotchi_status",
        {"op": "pair", "user_code": "BCDF-GHJK", "idempotency_key": key()},
    )
    assert out["ok"] is False
    assert out["error_code"] == "unsupported_online"
    assert called["approve"] == 0


def test_online_pair_revoke_via_tool_is_unsupported(server, store, monkeypatch) -> None:
    """teknium1 catalog review: agent must not revoke devices online."""
    pair_new_account(server, store)
    c = online(server, store)
    status = c.execute("hermagotchi_status", {"op": "pair"})
    assert status["ok"] is True
    device_id = status["data"]["devices"][0]["device_id"]
    called = {"revoke": 0}

    def boom(device_id: str):
        called["revoke"] += 1
        raise AssertionError(f"revoke must not run online via tool ({device_id!r})")

    monkeypatch.setattr(c.transport.pair, "revoke", boom)
    out = c.execute(
        "hermagotchi_status",
        {"op": "pair", "revoke_device_id": device_id, "idempotency_key": key()},
    )
    assert out["ok"] is False
    assert out["error_code"] == "unsupported_online"
    assert called["revoke"] == 0


def test_online_pair_status_read_still_works(server, store) -> None:
    pair_new_account(server, store)
    c = online(server, store)
    out = c.execute("hermagotchi_status", {"op": "pair"})
    assert out["ok"] is True
    assert out["data"]["paired"] is True
    assert isinstance(out["data"]["devices"], list)
    assert out["data"]["devices"]


def test_online_pair_unpaired_without_code_is_pair_via_pane(server, store) -> None:
    c = online(server, store)
    out = c.execute("hermagotchi_status", {"op": "pair"})
    assert out["ok"] is False
    assert out["error_code"] == "pair_via_pane"


def test_tools_module_docstring_mentions_online_backend() -> None:
    doc = tools.__doc__ or ""
    assert "network_enabled" in doc
    assert "OnlineGameClient" in doc or "online" in doc.lower()
    assert "do NOT talk to the hosted game" not in doc
    assert "unsupported_online" in doc
