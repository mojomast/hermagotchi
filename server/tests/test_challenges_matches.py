"""Async challenge, tactics and match resolution tests (HGT-W2-F)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "matches"
BOT_ID = "00000000-0000-4000-8000-00000000b07b"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _adopt(client, headers, species, name):
    response = client.post(
        "/v1/pets", headers=headers, json={"species": species, "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _invite(client, headers, defender_id, mode="casual"):
    return client.post(
        "/v1/challenges",
        headers=headers,
        json={"defender_id": defender_id, "mode": mode},
    )


def _accept(client, headers, challenge_id, action="accept"):
    return client.post(
        f"/v1/challenges/{challenge_id}/respond",
        headers=headers,
        json={"action": action},
    )


def _submit(client, headers, match_id, card):
    return client.post(
        f"/v1/matches/{match_id}/tactics",
        headers=headers,
        json={"card": card},
    )


def _db_rows(app, sql, params=()):
    conn = sqlite3.connect(app.state.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_create_challenge_returns_contract_and_pending_status(
    client, auth_headers_a, auth_headers_b, account_b, validate_contract
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")

    response = _invite(client, auth_headers_a, account_b, "ranked")

    assert response.status_code == 201, response.text
    challenge = response.json()
    validate_contract("Challenge", challenge)
    assert challenge["status"] == "pending"
    assert challenge["mode"] == "ranked"
    assert challenge["challenger_id"] != challenge["defender_id"]


def test_two_accounts_complete_one_match_with_identical_replay(
    app, client, auth_headers_a, auth_headers_b, account_b, validate_contract
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")
    challenge = _invite(client, auth_headers_a, account_b, "casual").json()

    accepted = _accept(client, auth_headers_b, challenge["id"])
    assert accepted.status_code == 200, accepted.text
    accepted_body = accepted.json()
    validate_contract("Challenge", accepted_body["challenge"])
    assert accepted_body["challenge"]["status"] == "accepted"
    validate_contract("Match", accepted_body["match"])
    match = accepted_body["match"]
    assert match["status"] == "pending"
    assert match["seed"] is None
    assert match["replay_hash"] is None
    match_id = match["id"]

    first = _submit(client, auth_headers_a, match_id, _load("tactic_aggressive.json"))
    assert first.status_code == 200, first.text
    assert first.json()["match"]["status"] == "pending"
    assert first.json()["replay"] is None

    duplicate = _submit(client, auth_headers_a, match_id, _load("tactic_aggressive.json"))
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["match"]["status"] == "pending"

    resolved = _submit(client, auth_headers_b, match_id, _load("tactic_defensive.json"))
    assert resolved.status_code == 200, resolved.text
    resolved_body = resolved.json()
    validate_contract("Match", resolved_body["match"])
    assert resolved_body["match"]["status"] == "resolved"
    assert resolved_body["match"]["replay_hash"]
    replay = resolved_body["replay"]
    assert replay["replay_hash"] == resolved_body["match"]["replay_hash"]
    assert replay["events"]

    seen_a = client.get(f"/v1/matches/{match_id}", headers=auth_headers_a)
    seen_b = client.get(f"/v1/matches/{match_id}", headers=auth_headers_b)
    assert seen_a.status_code == 200, seen_a.text
    assert seen_b.status_code == 200, seen_b.text
    assert seen_a.json()["replay"]["replay_hash"] == seen_b.json()["replay"]["replay_hash"]
    assert seen_a.json()["match"]["replay_hash"] == seen_b.json()["match"]["replay_hash"]
    assert seen_a.json()["replay"]["events"] == seen_b.json()["replay"]["events"]

    assert len(_db_rows(app, "SELECT * FROM tactics WHERE match_id = ?", (match_id,))) == 2
    events = _db_rows(app, "SELECT * FROM match_events WHERE match_id = ?", (match_id,))
    assert len(events) == len(replay["events"])
    assert [row["seq"] for row in events] == list(range(1, len(events) + 1))

    entitlements = _db_rows(
        app, "SELECT account_id, kind FROM reward_entitlements WHERE match_id = ?", (match_id,)
    )
    assert len(entitlements) == 4
    assert {row["kind"] for row in entitlements} == {"bits", "xp"}


def test_duplicate_tactics_and_repeated_reads_do_not_double_award(
    app, client, auth_headers_a, auth_headers_b, account_b
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "byteblob", "Blob")
    challenge = _invite(client, auth_headers_a, account_b, "ranked").json()
    match_id = _accept(client, auth_headers_b, challenge["id"]).json()["match"]["id"]

    _submit(client, auth_headers_a, match_id, _load("tactic_aggressive.json"))
    _submit(client, auth_headers_b, match_id, _load("tactic_defensive.json"))
    before = _db_rows(
        app, "SELECT id FROM reward_entitlements WHERE match_id = ? ORDER BY id", (match_id,)
    )
    original_hash = client.get(
        f"/v1/matches/{match_id}", headers=auth_headers_a
    ).json()["match"]["replay_hash"]

    for _ in range(5):
        response = _submit(
            client, auth_headers_a, match_id, _load("tactic_aggressive.json")
        )
        assert response.status_code == 200, response.text
        assert response.json()["match"]["replay_hash"] == original_hash

    after = _db_rows(
        app, "SELECT id FROM reward_entitlements WHERE match_id = ? ORDER BY id", (match_id,)
    )
    assert before == after
    events = _db_rows(app, "SELECT id FROM match_events WHERE match_id = ?", (match_id,))
    assert len(events) == len(set(row["id"] for row in events))


def test_practice_bot_resolves_immediately_and_never_changes_ratings(
    app, client, auth_headers_a
):
    _adopt(client, auth_headers_a, "byteblob", "Blob")

    created = _invite(client, auth_headers_a, None, "practice")
    assert created.status_code == 201, created.text
    challenge = created.json()
    assert challenge["mode"] == "practice"
    assert challenge["status"] == "accepted"
    assert challenge["defender_id"] == BOT_ID

    accepted = _accept(client, auth_headers_a, challenge["id"])
    assert accepted.status_code == 200, accepted.text
    match_id = accepted.json()["match"]["id"]

    ratings_before = _ratings_snapshot(app)
    resolved = _submit(client, auth_headers_a, match_id, _load("tactic_aggressive.json"))
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["match"]["status"] == "resolved"
    assert body["replay"]["winner"] in {"a", "b", None}
    assert _ratings_snapshot(app) == ratings_before

    entitlements = _db_rows(
        app, "SELECT kind FROM reward_entitlements WHERE match_id = ?", (match_id,)
    )
    assert {row["kind"] for row in entitlements} == {"bits", "xp"}

    duplicate = _submit(client, auth_headers_a, match_id, _load("tactic_aggressive.json"))
    assert duplicate.status_code == 200
    assert duplicate.json()["match"]["replay_hash"] == body["match"]["replay_hash"]
    assert len(
        _db_rows(app, "SELECT id FROM reward_entitlements WHERE match_id = ?", (match_id,))
    ) == 2


def _ratings_snapshot(app):
    rows = _db_rows(app, "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'ratings'")
    if not rows:
        return None
    return [
        tuple(row)
        for row in _db_rows(
            app, "SELECT account_id, season_id, rating, wins, losses FROM ratings ORDER BY account_id"
        )
    ]


def test_locked_tactic_cannot_be_replaced(
    client, auth_headers_a, auth_headers_b, account_b
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")
    challenge = _invite(client, auth_headers_a, account_b, "casual").json()
    match_id = _accept(client, auth_headers_b, challenge["id"]).json()["match"]["id"]

    assert _submit(client, auth_headers_a, match_id, _load("tactic_aggressive.json")).status_code == 200
    replacement = _submit(client, auth_headers_a, match_id, _load("tactic_defensive.json"))
    assert replacement.status_code == 409
    assert replacement.json()["code"] == "tactics_locked"


def test_invalid_tactic_is_rejected_with_engine_code(
    client, auth_headers_a, auth_headers_b, account_b
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")
    challenge = _invite(client, auth_headers_a, account_b, "casual").json()
    match_id = _accept(client, auth_headers_b, challenge["id"]).json()["match"]["id"]

    bad = {
        "ruleset_version": "battle-1",
        "stance": "balanced",
        "actions": [{"when": {"always": True}, "move": "hyper_beam"}],
    }
    response = _submit(client, auth_headers_a, match_id, bad)

    assert response.status_code == 422
    assert response.json()["code"] == "tactic_move_unknown"


def test_non_participant_cannot_submit_tactics(
    client, auth_headers_a, auth_headers_b, account_a, account_b
):
    outsider = "00000000-0000-4000-8000-0000000000c3"
    from server.app.db import connect, seed_account

    conn = connect(client.app.state.db_path)
    try:
        seed_account(conn, outsider)
    finally:
        conn.close()

    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")
    challenge = _invite(client, auth_headers_a, account_b, "casual").json()
    match_id = _accept(client, auth_headers_b, challenge["id"]).json()["match"]["id"]

    response = _submit(
        client, {"X-Account-Id": outsider}, match_id, _load("tactic_aggressive.json")
    )
    assert response.status_code == 403
    assert response.json()["code"] == "not_participant"


def test_decline_creates_no_match(
    app, client, auth_headers_a, auth_headers_b, account_b
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")
    challenge = _invite(client, auth_headers_a, account_b, "casual").json()

    declined = _accept(client, auth_headers_b, challenge["id"], "decline")
    assert declined.status_code == 200, declined.text
    assert declined.json()["challenge"]["status"] == "declined"
    assert declined.json()["match"] is None
    assert not _db_rows(app, "SELECT id FROM matches WHERE challenge_id = ?", (challenge["id"],))


def test_expired_challenge_cannot_be_accepted(
    app, client, auth_headers_a, auth_headers_b, account_b
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")
    challenge = _invite(client, auth_headers_a, account_b, "casual").json()

    conn = sqlite3.connect(app.state.db_path)
    try:
        conn.execute(
            "UPDATE challenges SET expires_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00.000Z", challenge["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    response = _accept(client, auth_headers_b, challenge["id"])
    assert response.status_code == 409
    assert response.json()["code"] == "challenge_expired"
    assert not _db_rows(app, "SELECT id FROM matches WHERE challenge_id = ?", (challenge["id"],))


def test_challenge_rejects_self_and_unknown_opponent(
    client, auth_headers_a, account_a
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")

    self_challenge = _invite(client, auth_headers_a, account_a, "casual")
    assert self_challenge.status_code == 422
    assert self_challenge.json()["code"] == "invalid_opponent"

    unknown = _invite(
        client, auth_headers_a, "00000000-0000-4000-8000-0000000000ff", "casual"
    )
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "opponent_not_found"


def test_tactics_require_accepted_challenge_and_matching_accounts(
    client, auth_headers_a, auth_headers_b, account_b
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")
    challenge = _invite(client, auth_headers_a, account_b, "casual").json()

    early = _submit(client, auth_headers_a, challenge["id"], _load("tactic_aggressive.json"))
    assert early.status_code == 404
    assert early.json()["code"] == "match_not_found"

    match_id = _accept(client, auth_headers_b, challenge["id"]).json()["match"]["id"]
    duplicate_accept = _accept(client, auth_headers_b, challenge["id"])
    assert duplicate_accept.status_code == 200
    assert duplicate_accept.json()["match"]["id"] == match_id
