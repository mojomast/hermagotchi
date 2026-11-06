"""Signup cap and trusted-proxy tests (HGT-W10-Z).

All requests go through the in-process FastAPI ``TestClient`` against a
temporary SQLite database. No network access is performed.
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from server.app.main import create_app

SIGNUP_ENV = (
    "HERMAGOTCHI_SIGNUP_CAP",
    "HERMAGOTCHI_SIGNUP_PER_IP",
    "HERMAGOTCHI_TRUSTED_PROXY",
)


@pytest.fixture
def signup_client(tmp_path, monkeypatch):
    for name in SIGNUP_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_CAP", "100")
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_PER_IP", "5")

    app = create_app(db_path=tmp_path / "signup-limits.db")
    with TestClient(app) as client:
        yield client, app


def _start(client, *, new_account=True, headers=None, device_name="Test Device"):
    return client.post(
        "/v1/auth/pair/start",
        json={"device_name": device_name, "new_account": new_account},
        headers=headers or {},
    )


def _exchange(client, device_code, *, headers=None):
    return client.post(
        "/v1/auth/pair/token",
        json={"device_code": device_code},
        headers=headers or {},
    )


def _create_account(client, *, headers=None):
    started = _start(client, headers=headers)
    assert started.status_code == 201
    tokens = _exchange(client, started.json()["device_code"], headers=headers)
    assert tokens.status_code == 200
    return tokens.json()


def _assert_error(response, code, message):
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == code
    assert body["message"] == message


def test_global_cap_blocks_third_new_account(signup_client, monkeypatch):
    client, _app = signup_client
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_CAP", "2")
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_PER_IP", "10")

    _create_account(client)
    _create_account(client)

    blocked = _start(client)
    _assert_error(
        blocked,
        "signup_closed",
        "New account sign-ups are closed right now.",
    )


def test_token_exchange_rechecks_global_cap(signup_client, monkeypatch):
    client, _app = signup_client
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_CAP", "1")
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_PER_IP", "10")

    first = _start(client)
    second = _start(client)
    assert first.status_code == 201
    assert second.status_code == 201

    created = _exchange(client, first.json()["device_code"])
    assert created.status_code == 200

    blocked = _exchange(client, second.json()["device_code"])
    _assert_error(
        blocked,
        "signup_closed",
        "New account sign-ups are closed right now.",
    )


def test_per_ip_cap_blocks_same_ip_and_allows_another(signup_client, monkeypatch):
    client, _app = signup_client
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_CAP", "100")
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_PER_IP", "1")

    _create_account(client)

    blocked = _start(client)
    _assert_error(
        blocked,
        "signup_ip_limit",
        "This network has reached the new-account limit.",
    )

    monkeypatch.setenv("HERMAGOTCHI_TRUSTED_PROXY", "1")
    allowed = _start(client, headers={"X-Forwarded-For": "198.51.100.7"})
    assert allowed.status_code == 201


def test_per_ip_cap_rechecked_at_token_exchange(signup_client, monkeypatch):
    client, _app = signup_client
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_CAP", "100")
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_PER_IP", "1")

    first = _start(client)
    second = _start(client)
    assert first.status_code == 201
    assert second.status_code == 201

    created = _exchange(client, first.json()["device_code"])
    assert created.status_code == 200

    blocked = _exchange(client, second.json()["device_code"])
    _assert_error(
        blocked,
        "signup_ip_limit",
        "This network has reached the new-account limit.",
    )


def test_untrusted_forwarded_headers_do_not_change_counted_ip(
    signup_client, monkeypatch
):
    client, _app = signup_client
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_PER_IP", "1")

    _create_account(client)

    forged = _start(
        client,
        headers={
            "X-Forwarded-For": "198.51.100.50, 203.0.113.9",
            "X-Real-IP": "198.51.100.51",
        },
    )
    _assert_error(
        forged,
        "signup_ip_limit",
        "This network has reached the new-account limit.",
    )


def test_trusted_proxy_uses_forwarded_headers(signup_client, monkeypatch):
    client, _app = signup_client
    monkeypatch.setenv("HERMAGOTCHI_SIGNUP_PER_IP", "1")
    monkeypatch.setenv("HERMAGOTCHI_TRUSTED_PROXY", "1")

    _create_account(client, headers={"X-Forwarded-For": "198.51.100.10"})

    same_ip = _start(client, headers={"X-Forwarded-For": "198.51.100.10"})
    _assert_error(
        same_ip,
        "signup_ip_limit",
        "This network has reached the new-account limit.",
    )

    other_ip = _start(client, headers={"X-Real-IP": "198.51.100.11"})
    assert other_ip.status_code == 201

    chain = "198.51.100.12, 10.0.0.5"
    _create_account(client, headers={"X-Forwarded-For": chain})
    leftmost_repeat = _start(client, headers={"X-Forwarded-For": chain})
    _assert_error(
        leftmost_repeat,
        "signup_ip_limit",
        "This network has reached the new-account limit.",
    )


def test_signup_stats_and_created_ip_are_persisted(signup_client, monkeypatch):
    client, app = signup_client
    monkeypatch.setenv("HERMAGOTCHI_TRUSTED_PROXY", "1")

    tokens = _create_account(client, headers={"X-Forwarded-For": "198.51.100.20"})

    conn = sqlite3.connect(app.state.db_path)
    conn.row_factory = sqlite3.Row
    try:
        account = conn.execute(
            "SELECT created_ip FROM accounts WHERE id = ?",
            (tokens["account_id"],),
        ).fetchone()
        stats = conn.execute(
            "SELECT signup_count FROM signup_ip_stats WHERE ip = ?",
            ("198.51.100.20",),
        ).fetchone()
    finally:
        conn.close()

    assert account is not None
    assert account["created_ip"] == "198.51.100.20"
    assert stats is not None
    assert stats["signup_count"] == 1
