"""Casual PvP ratings and leaderboard projection tests (HGT-W11-B).

All requests use FastAPI's in-process TestClient; no real network is used.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "matches"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _adopt(client, headers, species, name):
    response = client.post(
        "/v1/pets", headers=headers, json={"species": species, "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _invite(client, headers, defender_id=None, mode="casual"):
    body = {"mode": mode}
    if defender_id is not None:
        body["defender_id"] = defender_id
    return client.post("/v1/challenges", headers=headers, json=body)


def _accept(client, headers, challenge_id):
    return client.post(
        f"/v1/challenges/{challenge_id}/respond",
        headers=headers,
        json={"action": "accept"},
    )


def _submit(client, headers, match_id, card_name):
    return client.post(
        f"/v1/matches/{match_id}/tactics",
        headers=headers,
        json={"card": _load(card_name)},
    )


def _ratings(app):
    conn = sqlite3.connect(app.state.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            """
            SELECT account_id, season_id, rating, wins, losses
            FROM ratings ORDER BY account_id
            """
        ).fetchall()
    finally:
        conn.close()


def _play(client, app, headers_a, headers_b, account_b, mode, adopt=True):
    if adopt:
        _adopt(client, headers_a, "patchfox", "Ash")
        _adopt(client, headers_b, "nullgeist", "Wisp")
    challenge = _invite(client, headers_a, account_b, mode).json()
    match_id = _accept(client, headers_b, challenge["id"]).json()["match"]["id"]
    assert _submit(client, headers_a, match_id, "tactic_aggressive.json").status_code == 200
    resolved = _submit(client, headers_b, match_id, "tactic_defensive.json")
    assert resolved.status_code == 200, resolved.text
    return resolved.json()


def test_casual_pvp_writes_ratings_and_shows_both_on_leaderboard(
    app, client, auth_headers_a, auth_headers_b, account_a, account_b
):
    body = _play(client, app, auth_headers_a, auth_headers_b, account_b, "casual")
    assert body["match"]["status"] == "resolved"
    assert body["match"]["winner"] == body["replay"]["winner"]

    rows = _ratings(app)
    assert {row["account_id"] for row in rows} == {account_a, account_b}
    assert {row["season_id"] for row in rows} == {"season-1"}
    games = {row["account_id"]: row["wins"] + row["losses"] for row in rows}
    assert games == {account_a: 1, account_b: 1}
    assert sum(row["wins"] for row in rows) == 1
    assert sum(row["losses"] for row in rows) == 1

    leaderboard = client.get("/v1/leaderboard?season_id=season-1", headers=auth_headers_a)
    assert leaderboard.status_code == 200, leaderboard.text
    payload = leaderboard.json()
    assert payload["total"] >= 2
    visible = {entry["account"]["id"] for entry in payload["entries"]}
    assert {account_a, account_b} <= visible
    assert payload["me"]["account"]["id"] == account_a


def test_second_casual_match_updates_the_same_rating_rows(
    app, client, auth_headers_a, auth_headers_b, account_b
):
    _play(client, app, auth_headers_a, auth_headers_b, account_b, "casual")
    first = {row["account_id"]: row for row in _ratings(app)}

    _play(
        client,
        app,
        auth_headers_a,
        auth_headers_b,
        account_b,
        "casual",
        adopt=False,
    )
    second = {row["account_id"]: row for row in _ratings(app)}

    assert set(first) == set(second)
    assert len(_ratings(app)) == 2
    assert all(second[key]["wins"] + second[key]["losses"] == 2 for key in second)


def test_ranked_pvp_still_writes_ratings(
    app, client, auth_headers_a, auth_headers_b, account_b
):
    _play(client, app, auth_headers_a, auth_headers_b, account_b, "ranked")

    rows = _ratings(app)
    assert len(rows) == 2
    assert sum(row["wins"] for row in rows) == 1
    assert sum(row["losses"] for row in rows) == 1


def test_practice_never_creates_or_changes_ratings(
    app, client, auth_headers_a, account_a
):
    _adopt(client, auth_headers_a, "byteblob", "Blob")

    challenge = _invite(client, auth_headers_a, None, "practice").json()
    match_id = _accept(client, auth_headers_a, challenge["id"]).json()["match"]["id"]
    resolved = _submit(client, auth_headers_a, match_id, "tactic_aggressive.json")

    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["match"]["status"] == "resolved"
    assert _ratings(app) == []

    leaderboard = client.get("/v1/leaderboard?season_id=season-1", headers=auth_headers_a)
    assert leaderboard.status_code == 200, leaderboard.text
    assert leaderboard.json()["me"] is None
    assert leaderboard.json()["total"] == 0
