"""Arena inbox and deterministic Teknium practice routes (HGT-W8-T)."""

from __future__ import annotations

import sqlite3

from server.app.combat import BATTLE_2_VERSION, effectiveness

BOT_ID = "00000000-0000-4000-8000-00000000b07b"


def _adopt(client, headers, species="nullgeist", name="Wisp"):
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


def _inbox(client, headers):
    response = client.get("/v1/challenges/inbox", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _practice(client, headers, pet_id, tactics=None):
    body = {"pet_id": pet_id}
    if tactics is not None:
        body["tactics"] = tactics
    return client.post("/v1/practice", headers=headers, json=body)


TACTIC = {
    "ruleset_version": BATTLE_2_VERSION,
    "stance": "balanced",
    "actions": [{"when": {"always": True}, "move": "basic_attack"}],
}


def test_inbox_splits_pending_incoming_and_outgoing(
    client, auth_headers_a, auth_headers_b, account_a, account_b
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")

    sent = _invite(client, auth_headers_a, account_b, "casual")
    assert sent.status_code == 201, sent.text
    challenge_id = sent.json()["id"]

    inbox_b = _inbox(client, auth_headers_b)
    assert [item["id"] for item in inbox_b["incoming"]] == [challenge_id]
    assert inbox_b["outgoing"] == []
    assert inbox_b["incoming"][0]["direction"] == "incoming"
    assert inbox_b["count"] == 1

    inbox_a = _inbox(client, auth_headers_a)
    assert inbox_a["incoming"] == []
    assert [item["id"] for item in inbox_a["outgoing"]] == [challenge_id]
    assert inbox_a["outgoing"][0]["direction"] == "outgoing"

    declined = client.post(
        f"/v1/challenges/{challenge_id}/respond",
        headers=auth_headers_b,
        json={"action": "decline"},
    )
    assert declined.status_code == 200, declined.text
    assert _inbox(client, auth_headers_b)["challenges"] == []
    assert _inbox(client, auth_headers_a)["challenges"] == []


def test_inbox_hides_expired_and_other_accounts_challenges(
    app, client, auth_headers_a, auth_headers_b, account_b
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")
    challenge = _invite(client, auth_headers_a, account_b, "casual").json()

    outsider = "00000000-0000-4000-8000-0000000000c3"
    from server.app.db import connect, seed_account

    conn = connect(app.state.db_path)
    try:
        seed_account(conn, outsider)
        conn.execute(
            "UPDATE challenges SET expires_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00.000Z", challenge["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    assert _inbox(client, auth_headers_a)["challenges"] == []
    assert _inbox(client, auth_headers_b)["challenges"] == []
    assert _inbox(client, {"X-Account-Id": outsider})["challenges"] == []

    statuses = client.app.state.db_path
    conn = sqlite3.connect(statuses)
    try:
        status = conn.execute(
            "SELECT status FROM challenges WHERE id = ?", (challenge["id"],)
        ).fetchone()[0]
    finally:
        conn.close()
    assert status == "expired"


def test_practice_is_deterministic_battle_2_with_type_effectiveness(
    client, auth_headers_a
):
    pet = _adopt(client, auth_headers_a, "nullgeist", "Wisp")

    first = _practice(client, auth_headers_a, pet["id"], TACTIC)
    assert first.status_code == 200, first.text
    body = first.json()

    assert body["match_id"] == body["match"]["id"]
    assert body["match"]["status"] == "resolved"
    assert body["match"]["ruleset_version"] == BATTLE_2_VERSION
    assert body["match"]["result"] in {"ko", "decision"}
    assert body["match"]["bot"]["name"] == "Teknium"
    assert body["match"]["bot"]["id"] == BOT_ID
    assert body["match"]["bot"]["type"] == "kernel"

    replay = body["replay"]
    assert replay["ruleset_version"] == BATTLE_2_VERSION
    assert replay["events"]
    assert replay["replay_hash"] == body["match"]["replay_hash"]

    log = body["turn_log"]
    assert len(log) == len(replay["events"])
    attacks = [event for event in log if event["move"] in {"basic_attack", "quick_strike", "glitch_pulse"}]
    assert attacks
    expected_super = effectiveness("glitch", "kernel")
    expected_resisted = effectiveness("kernel", "glitch")
    assert expected_super == (17, 16)
    assert expected_resisted == (16, 17)

    labels = {event["effectiveness"] for event in attacks}
    assert "super" in labels
    assert "resisted" in labels
    for event in attacks:
        fraction = event["multiplier_fraction"]
        assert fraction is not None
        assert fraction["denominator"] > 0
        assert event["multiplier"] == fraction["value"]
        if event["attacker_type"] == "glitch":
            assert (fraction["numerator"], fraction["denominator"]) == expected_super
            assert event["effectiveness"] == "super"
        elif event["attacker_type"] == "kernel":
            assert (fraction["numerator"], fraction["denominator"]) == expected_resisted
            assert event["effectiveness"] == "resisted"

    second = _practice(client, auth_headers_a, pet["id"], TACTIC)
    assert second.status_code == 200, second.text
    assert second.json()["replay"]["replay_hash"] == replay["replay_hash"]
    assert second.json()["replay"]["events"] == replay["events"]
    assert second.json()["turn_log"] == log
    assert second.json()["match"]["id"] != body["match"]["id"]

    replay_read = client.get(f"/v1/matches/{body['match']['id']}", headers=auth_headers_a)
    assert replay_read.status_code == 200, replay_read.text
    assert replay_read.json()["replay"]["replay_hash"] == replay["replay_hash"]
    assert replay_read.json()["match"]["status"] == "resolved"


def test_practice_rewards_follow_existing_practice_rules_and_never_rate(
    client, auth_headers_a
):
    pet = _adopt(client, auth_headers_a, "byteblob", "Blob")

    response = _practice(client, auth_headers_a, pet["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert {reward["kind"] for reward in body["rewards"]} == {"bits", "xp"}
    assert {reward["amount"] for reward in body["rewards"]} == {10, 15}

    wallet = client.get("/v1/wallet", headers=auth_headers_a)
    assert wallet.status_code == 200, wallet.text
    assert wallet.json()["balance"] == 10

    ratings = client.get("/v1/leaderboard?season_id=season-1", headers=auth_headers_a)
    assert ratings.status_code == 200, ratings.text
    assert ratings.json()["me"] is None


def test_practice_is_owner_only_and_matches_are_private(
    client, auth_headers_a, auth_headers_b
):
    pet_a = _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "byteblob", "Blob")

    stolen = _practice(client, auth_headers_b, pet_a["id"])
    assert stolen.status_code == 403
    assert stolen.json()["code"] == "pet_not_owned"

    missing = _practice(client, auth_headers_a, "10000000-0000-4000-8000-0000000000ff")
    assert missing.status_code == 404
    assert missing.json()["code"] == "pet_not_found"

    own = _practice(client, auth_headers_a, pet_a["id"])
    assert own.status_code == 200, own.text
    match_id = own.json()["match"]["id"]

    private = client.get(f"/v1/matches/{match_id}", headers=auth_headers_b)
    assert private.status_code == 403
    assert private.json()["code"] == "not_participant"


def test_practice_rejects_invalid_tactics_and_bot_is_not_in_inbox(
    client, auth_headers_a
):
    pet = _adopt(client, auth_headers_a, "patchfox", "Ash")
    bad = {
        "ruleset_version": BATTLE_2_VERSION,
        "stance": "balanced",
        "actions": [{"when": {"always": True}, "move": "hyper_beam"}],
    }
    response = _practice(client, auth_headers_a, pet["id"], bad)
    assert response.status_code == 422
    assert response.json()["code"] == "tactic_move_unknown"

    ok = _practice(client, auth_headers_a, pet["id"])
    assert ok.status_code == 200, ok.text
    assert _inbox(client, auth_headers_a)["challenges"] == []
