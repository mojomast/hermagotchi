"""Device-pairing auth contract tests (HGT-W7-P).

Every test uses the in-process FastAPI ``TestClient`` and the temporary SQLite
database from ``conftest.py``. No network access is performed and no token is
ever written to a log or assertion message.
"""

from __future__ import annotations

import sqlite3
import uuid

import pytest

from server.app import auth as auth_module

ALPHABET = set("BCDFGHJKLMNPQRSTVWXZ23456789")


def _start(client, *, new_account=False, device_name="Test Device", public_handle=None):
    body = {"device_name": device_name, "new_account": new_account}
    if public_handle is not None:
        body["public_handle"] = public_handle
    return client.post("/v1/auth/pair/start", json=body)


def _exchange(client, device_code):
    return client.post("/v1/auth/pair/token", json={"device_code": device_code})


def _pair(client, *, new_account=True, device_name="Test Device"):
    started = _start(client, new_account=new_account, device_name=device_name)
    assert started.status_code == 201
    pairing = started.json()
    tokens = _exchange(client, pairing["device_code"])
    assert tokens.status_code == 200
    return pairing, tokens.json()


def _bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _rows(app, sql, params=()):
    conn = sqlite3.connect(app.state.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _assert_user_code(value):
    compact = value.replace("-", "")
    assert len(compact) == 8
    assert set(compact) <= ALPHABET
    assert value[4] == "-"


def test_pair_start_new_account_happy_path(client):
    started = _start(client, new_account=True, device_name="Ada Laptop")

    assert started.status_code == 201
    pairing = started.json()
    assert pairing["device_code"].startswith("hgd_")
    _assert_user_code(pairing["user_code"])
    assert pairing["expires_at"]
    assert pairing["interval_s"] == 5
    assert pairing["new_account"] is True

    token_response = _exchange(client, pairing["device_code"])
    assert token_response.status_code == 200
    tokens = token_response.json()
    assert tokens["access_token"].startswith("hga_")
    assert tokens["refresh_token"].startswith("hgr_")
    assert tokens["token_type"] == "Bearer"
    assert tokens["expires_in"] > 0
    assert tokens["refresh_expires_in"] > 0
    assert uuid.UUID(tokens["account_id"])
    assert uuid.UUID(tokens["device_id"])

    me = client.get("/v1/me", headers=_bearer(tokens))
    assert me.status_code == 200
    assert me.json()["account"]["id"] == tokens["account_id"]

    devices = client.get("/v1/auth/devices", headers=_bearer(tokens))
    assert devices.status_code == 200
    assert len(devices.json()["devices"]) == 1
    device = devices.json()["devices"][0]
    assert device["device_id"] == tokens["device_id"]
    assert device["device_name"] == "Ada Laptop"
    assert device["current"] is True
    assert device["revoked"] is False


def test_approve_second_device_joins_same_account(client):
    _, first = _pair(client, device_name="First")

    started = _start(client, new_account=False, device_name="Second")
    assert started.status_code == 201
    pairing = started.json()

    approved = client.post(
        "/v1/auth/pair/approve",
        headers=_bearer(first),
        json={"user_code": pairing["user_code"].lower().replace("-", " ")},
    )
    assert approved.status_code == 200
    assert approved.json() == {"approved": True, "device_name": "Second"}

    second_response = _exchange(client, pairing["device_code"])
    assert second_response.status_code == 200
    second = second_response.json()
    assert second["account_id"] == first["account_id"]
    assert second["device_id"] != first["device_id"]

    devices = client.get("/v1/auth/devices", headers=_bearer(first)).json()["devices"]
    assert len(devices) == 2
    assert {device["device_id"] for device in devices} == {
        first["device_id"],
        second["device_id"],
    }


def test_pairing_expires_with_time(client, monkeypatch):
    clock = [1_800_000_000.0]
    monkeypatch.setattr(auth_module, "now_ts", lambda: clock[0])

    _, first = _pair(client, device_name="First")
    started = _start(client, new_account=False, device_name="Late")
    pairing = started.json()

    clock[0] += 601
    expired = client.post(
        "/v1/auth/pair/approve",
        headers=_bearer(first),
        json={"user_code": pairing["user_code"]},
    )
    assert expired.status_code == 400
    assert expired.json()["code"] == "expired_token"


def test_wrong_user_code_then_lockout(client):
    _, first = _pair(client, device_name="First")
    pairing = _start(client, new_account=False, device_name="Second").json()

    wrong = "BBBB-BBBB"
    if wrong == pairing["user_code"]:
        wrong = "CCCC-CCCC"
    for _ in range(5):
        response = client.post(
            "/v1/auth/pair/approve",
            headers=_bearer(first),
            json={"user_code": wrong},
        )
        assert response.status_code == 404
        assert response.json()["code"] == "invalid_user_code"

    locked = client.post(
        "/v1/auth/pair/approve",
        headers=_bearer(first),
        json={"user_code": pairing["user_code"]},
    )
    assert locked.status_code == 429
    assert locked.json()["retry_after_s"] >= 1


def test_device_code_replay_is_invalid_grant(client):
    pairing, _ = _pair(client)

    replay = _exchange(client, pairing["device_code"])
    assert replay.status_code == 400
    assert replay.json()["code"] == "invalid_grant"


def test_token_polling_slow_down(client):
    started = _start(client, new_account=False).json()

    first = _exchange(client, started["device_code"])
    assert first.status_code == 400
    assert first.json()["code"] == "authorization_pending"

    too_fast = _exchange(client, started["device_code"])
    assert too_fast.status_code == 429
    assert too_fast.json()["code"] == "slow_down"
    assert too_fast.json()["retry_after_s"] >= 1


def test_refresh_rotation_and_reuse_revokes_device(client):
    _, first = _pair(client)

    rotated_response = client.post(
        "/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert rotated_response.status_code == 200
    rotated = rotated_response.json()
    assert rotated["access_token"] != first["access_token"]
    assert rotated["refresh_token"] != first["refresh_token"]
    assert rotated["account_id"] == first["account_id"]
    assert rotated["device_id"] == first["device_id"]

    reused = client.post(
        "/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert reused.status_code == 401
    assert reused.json()["code"] == "invalid_grant"

    revoked_access = client.get("/v1/me", headers=_bearer(rotated))
    assert revoked_access.status_code == 401

    revoked_refresh = client.post(
        "/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
    )
    assert revoked_refresh.status_code == 401


def test_device_revocation_kills_access_and_refresh(client):
    _, first = _pair(client, device_name="First")
    pairing = _start(client, new_account=False, device_name="Second").json()
    client.post(
        "/v1/auth/pair/approve",
        headers=_bearer(first),
        json={"user_code": pairing["user_code"]},
    )
    second = _exchange(client, pairing["device_code"]).json()

    listed = client.get("/v1/auth/devices", headers=_bearer(first)).json()["devices"]
    second_entry = next(
        device for device in listed if device["device_id"] == second["device_id"]
    )
    assert second_entry["current"] is False

    revoked = client.post(
        f"/v1/auth/devices/{second['device_id']}/revoke",
        headers=_bearer(first),
    )
    assert revoked.status_code == 200
    assert revoked.json() == {"revoked": True}

    assert client.get("/v1/me", headers=_bearer(second)).status_code == 401
    refresh = client.post(
        "/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
    )
    assert refresh.status_code == 401

    assert client.get("/v1/me", headers=_bearer(first)).status_code == 200


def test_cross_account_device_and_wallet_isolation(client, app):
    _, a = _pair(client, device_name="A Device")
    _, b = _pair(client, device_name="B Device")
    assert a["account_id"] != b["account_id"]

    b_devices = client.get("/v1/auth/devices", headers=_bearer(b)).json()["devices"]
    assert [device["device_id"] for device in b_devices] == [b["device_id"]]

    cross = client.post(
        f"/v1/auth/devices/{a['device_id']}/revoke",
        headers=_bearer(b),
    )
    assert cross.status_code == 404

    wallet_a = client.get("/v1/wallet", headers=_bearer(a))
    wallet_b = client.get("/v1/wallet", headers=_bearer(b))
    assert wallet_a.status_code == 200
    assert wallet_b.status_code == 200
    assert wallet_a.json()["account_id"] == a["account_id"]
    assert wallet_b.json()["account_id"] == b["account_id"]

    override = client.get(
        "/v1/wallet",
        headers={**_bearer(a), "X-Account-Id": b["account_id"]},
    )
    assert override.json()["account_id"] == a["account_id"]


def test_logout_revokes_current_device(client):
    _, first = _pair(client)

    logged_out = client.post("/v1/auth/logout", headers=_bearer(first))
    assert logged_out.status_code == 200
    assert logged_out.json() == {"revoked": True}

    assert client.get("/v1/me", headers=_bearer(first)).status_code == 401


def test_production_mode_ignores_stub_and_accepts_session(client, app, monkeypatch):
    _, a = _pair(client)

    conn = sqlite3.connect(app.state.db_path)
    try:
        conn.execute(
            """
            INSERT INTO ratings (account_id, season_id, rating, wins, losses)
            VALUES (?, 'season-1', 1000, 0, 0)
            """,
            (a["account_id"],),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("HERMAGOTCHI_AUTH_MODE", "production")

    stub = client.get("/v1/me", headers={"X-Account-Id": a["account_id"]})
    assert stub.status_code == 401

    raw_uuid = client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {uuid.uuid4()}"},
    )
    assert raw_uuid.status_code == 401

    session = client.get("/v1/me", headers=_bearer(a))
    assert session.status_code == 200
    assert session.json()["account"]["id"] == a["account_id"]

    leaderboard = client.get("/v1/leaderboard", headers=_bearer(a))
    assert leaderboard.status_code == 200
    assert leaderboard.json()["me"]["account"]["id"] == a["account_id"]


def test_tokens_are_stored_only_as_hashes(client, app):
    pairing, tokens = _pair(client)

    sessions = _rows(
        app,
        "SELECT access_token_hash, refresh_token_hash FROM auth_sessions",
    )
    pairings = _rows(app, "SELECT device_code_hash FROM pairings")
    assert len(sessions) == 1
    assert len(pairings) == 1

    for value in (
        sessions[0]["access_token_hash"],
        sessions[0]["refresh_token_hash"],
    ):
        assert len(value) == 64
        int(value, 16)
    assert len(pairings[0]["device_code_hash"]) == 64

    raw_values = {
        pairing["device_code"],
        tokens["access_token"],
        tokens["refresh_token"],
    }
    serialized = " ".join(
        str(value)
        for table in ("auth_sessions", "pairings")
        for row in _rows(app, f"SELECT * FROM {table}")
        for value in tuple(row)
    )
    assert all(raw not in serialized for raw in raw_values)


def test_pair_start_rate_limit_per_ip(client):
    for _ in range(10):
        assert _start(client).status_code == 201

    limited = _start(client)
    assert limited.status_code == 429
    assert limited.json()["retry_after_s"] >= 1


def test_approve_failure_lock_is_keyed_by_ip_too(client):
    _, first = _pair(client, device_name="First")
    pending = _start(client, new_account=False, device_name="Second").json()

    wrong_codes = ["BBBB-BBBB", "CCCC-CCCC", "DDDD-DDDD", "FFFF-FFFF", "HHHH-HHHH"]
    wrong_codes = [code for code in wrong_codes if code != pending["user_code"]]
    assert len(wrong_codes) >= 5

    for code in wrong_codes[:5]:
        response = client.post(
            "/v1/auth/pair/approve",
            headers=_bearer(first),
            json={"user_code": code},
        )
        assert response.status_code == 404
        assert response.json()["code"] == "invalid_user_code"

    locked = client.post(
        "/v1/auth/pair/approve",
        headers=_bearer(first),
        json={"user_code": pending["user_code"]},
    )
    assert locked.status_code == 429
    assert locked.json()["retry_after_s"] >= 1
