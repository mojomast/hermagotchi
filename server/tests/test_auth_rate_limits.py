"""Durable auth rate-limit tests (HGT-W11-A).

The limiter state must live in SQLite so a lock recorded by one uvicorn worker
is visible to every other worker. Each test uses the in-process FastAPI
``TestClient`` and a temporary database; no network access is performed.
"""

from __future__ import annotations

import sqlite3

from server.app import auth as auth_module


def _start(client, *, new_account=False, device_name="Test Device"):
    return client.post(
        "/v1/auth/pair/start",
        json={"device_name": device_name, "new_account": new_account},
    )


def _exchange(client, device_code):
    return client.post("/v1/auth/pair/token", json={"device_code": device_code})


def _pair(client, *, device_name="Test Device"):
    started = _start(client, new_account=True, device_name=device_name)
    assert started.status_code == 201, started.text
    tokens = _exchange(client, started.json()["device_code"])
    assert tokens.status_code == 200, tokens.text
    return tokens.json()


def _bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _row_count(app, sql, params=()):
    conn = sqlite3.connect(app.state.db_path)
    try:
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


def test_approve_lockout_survives_new_limiter_instance(client, app):
    first = _pair(client, device_name="First")
    pending = _start(client, device_name="Second").json()

    wrong = "BBBB-BBBB"
    if wrong == pending["user_code"]:
        wrong = "CCCC-CCCC"

    for _ in range(auth_module.APPROVE_FAILURE_LIMIT):
        response = client.post(
            "/v1/auth/pair/approve",
            headers=_bearer(first),
            json={"user_code": wrong},
        )
        assert response.status_code == 404
        assert response.json()["code"] == "invalid_user_code"

    # Simulate the next request landing on a different uvicorn worker.
    app.state.auth_rate_limiter = auth_module.AuthRateLimiter()

    locked = client.post(
        "/v1/auth/pair/approve",
        headers=_bearer(first),
        json={"user_code": pending["user_code"]},
    )
    assert locked.status_code == 429
    assert locked.json()["retry_after_s"] >= 1


def test_pair_start_limit_survives_new_limiter_instance(client, app):
    for _ in range(auth_module.PAIR_START_LIMIT):
        started = _start(client)
        assert started.status_code == 201, started.text

    app.state.auth_rate_limiter = auth_module.AuthRateLimiter()

    limited = _start(client)
    assert limited.status_code == 429
    assert limited.json()["retry_after_s"] >= 1


def test_rate_limit_state_is_persisted_in_sqlite(client, app):
    started = _start(client)
    assert started.status_code == 201

    assert _row_count(app, "SELECT COUNT(*) FROM auth_rate_hits") >= 1

    approver = _pair(client, device_name="Approver")
    pending = _start(client, device_name="Pending").json()
    wrong = "BBBB-BBBB"
    if wrong == pending["user_code"]:
        wrong = "CCCC-CCCC"
    for _ in range(auth_module.APPROVE_FAILURE_LIMIT):
        client.post(
            "/v1/auth/pair/approve",
            headers=_bearer(approver),
            json={"user_code": wrong},
        )

    # Distinct approve calls could be served by different workers; the lock row
    # must still exist in the shared database.
    assert _row_count(app, "SELECT COUNT(*) FROM auth_rate_locks") >= 1
