"""Server-side daily/weekly income caps (HGT-W12-B).

All requests use FastAPI's in-process TestClient against a temporary SQLite
database. No network access is performed.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from server.app.combat import BATTLE_2_VERSION
from server.app.db import connect
from server.app.economy import credit
from server.app.matchmaking import reward_bridge

FIXTURES = Path(__file__).parent / "fixtures" / "matches"

TACTIC = {
    "ruleset_version": BATTLE_2_VERSION,
    "stance": "balanced",
    "actions": [{"when": {"always": True}, "move": "basic_attack"}],
}


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _adopt(client, headers, species="byteblob", name="Nibbles"):
    response = client.post(
        "/v1/pets", headers=headers, json={"species": species, "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _practice(client, headers, pet_id):
    return client.post(
        "/v1/practice",
        headers=headers,
        json={"pet_id": pet_id, "tactics": TACTIC},
    )


def _play_casual(client, headers_a, headers_b, account_b):
    challenge = client.post(
        "/v1/challenges",
        headers=headers_a,
        json={"defender_id": account_b, "mode": "casual"},
    ).json()
    accepted = client.post(
        f"/v1/challenges/{challenge['id']}/respond",
        headers=headers_b,
        json={"action": "accept"},
    )
    assert accepted.status_code == 200, accepted.text
    match_id = accepted.json()["match"]["id"]
    first = client.post(
        f"/v1/matches/{match_id}/tactics",
        headers=headers_a,
        json={"card": _load("tactic_aggressive.json")},
    )
    assert first.status_code == 200, first.text
    resolved = client.post(
        f"/v1/matches/{match_id}/tactics",
        headers=headers_b,
        json={"card": _load("tactic_defensive.json")},
    )
    assert resolved.status_code == 200, resolved.text
    return match_id, resolved.json()


def _rows(app, sql, params=()):
    conn = sqlite3.connect(app.state.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _wallet(client, headers):
    response = client.get("/v1/wallet", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _reward_for(receipts, account_id, kind):
    for receipt in receipts:
        if receipt["account_id"] == account_id and receipt["kind"] == kind:
            return receipt
    return None


def test_fourth_practice_same_day_pays_zero_bits_and_xp(
    app, client, auth_headers_a
):
    pet = _adopt(client, auth_headers_a)

    for _ in range(3):
        response = _practice(client, auth_headers_a, pet["id"])
        assert response.status_code == 200, response.text
        assert {reward["amount"] for reward in response.json()["rewards"]} == {
            50,
            15,
        }

    capped = _practice(client, auth_headers_a, pet["id"])
    assert capped.status_code == 200, capped.text
    body = capped.json()
    rewards = body["rewards"]
    assert {reward["kind"] for reward in rewards} == {"bits", "xp"}
    assert {reward["amount"] for reward in rewards} == {0}
    assert {reward["reward_status"] for reward in rewards} == {"capped"}
    assert {reward["reward_reason"] for reward in rewards} == {
        "practice.daily_cap"
    }
    assert body["match"]["reward_reason"] == "practice.daily_cap"
    assert body["replay"]["reward_reason"] == "practice.daily_cap"

    # 300 starter Bits + three rewarded practices at 50 Bits each.
    assert _wallet(client, auth_headers_a)["balance"] == 450
    paid = _rows(
        app,
        "SELECT delta FROM ledger WHERE reason = 'battle.practice.bits'",
    )
    assert sum(row["delta"] for row in paid) == 150


def test_practice_weekly_bits_cap_stops_at_750(app, account_a):
    conn = connect(app.state.db_path)
    try:
        # Simulate 14 paid practices (700 Bits) earlier in one ISO week.
        week_monday = datetime(2026, 1, 5, tzinfo=timezone.utc)
        for index in range(14):
            source = f"seed.practice.week:{index}"
            credit(conn, account_a, 50, "battle.practice.bits", source)
            stamped = week_monday + timedelta(days=index % 5, minutes=index)
            conn.execute(
                "UPDATE ledger SET created_at = ? WHERE source_event_id = ?",
                (stamped.isoformat(timespec="milliseconds").replace("+00:00", "Z"), source),
            )
        conn.commit()

        awards = [
            {
                "account_id": account_a,
                "kind": "bits",
                "amount": 50,
                "reason": "battle.practice.bits",
                "mode": "practice",
            },
            {
                "account_id": account_a,
                "kind": "xp",
                "amount": 15,
                "reason": "battle.practice.xp",
                "mode": "practice",
            },
        ]
        allowed = reward_bridge.award_match_rewards(
            conn, "weekly-match-1", awards, "2026-01-10T12:00:00.000Z"
        )
        assert _reward_for(allowed, account_a, "bits")["amount"] == 50
        assert _reward_for(allowed, account_a, "xp")["amount"] == 15

        capped = reward_bridge.award_match_rewards(
            conn, "weekly-match-2", awards, "2026-01-10T12:05:00.000Z"
        )
        assert _reward_for(capped, account_a, "bits")["amount"] == 0
        assert _reward_for(capped, account_a, "xp")["amount"] == 0
        assert {
            receipt["reward_reason"]
            for receipt in capped
            if receipt["account_id"] == account_a
        } == {"practice.weekly_cap"}

        total = conn.execute(
            """
            SELECT COALESCE(SUM(delta), 0) AS total FROM ledger
            WHERE account_id = ? AND reason = 'battle.practice.bits'
            """,
            (account_a,),
        ).fetchone()["total"]
        assert total == 750
    finally:
        conn.close()


def test_eleventh_pvp_match_pays_zero_but_updates_ratings(
    app, client, auth_headers_a, auth_headers_b, account_a, account_b
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")

    conn = connect(app.state.db_path)
    try:
        # Simulate ten paid PvP matches earlier today.
        for index in range(10):
            credit(
                conn,
                account_a,
                80,
                "battle.casual.win.bits",
                f"seed.pvp.daily:{index}",
            )
    finally:
        conn.close()

    balance_before = _wallet(client, auth_headers_a)["balance"]
    match_id, body = _play_casual(
        client, auth_headers_a, auth_headers_b, account_b
    )

    assert body["match"]["status"] == "resolved"
    bits_award = _reward_for(body["replay"]["rewards"], account_a, "bits")
    xp_award = _reward_for(body["replay"]["rewards"], account_a, "xp")
    assert bits_award["amount"] == 0
    assert xp_award["amount"] == 0
    assert bits_award["reward_reason"] == "pvp.daily_cap"

    seen_as_a = client.get(f"/v1/matches/{match_id}", headers=auth_headers_a)
    assert seen_as_a.status_code == 200, seen_as_a.text
    assert seen_as_a.json()["match"]["reward_reason"] == "pvp.daily_cap"
    assert seen_as_a.json()["match"]["reward_status"] == "capped"

    assert _wallet(client, auth_headers_a)["balance"] == balance_before
    markers = _rows(
        app,
        """
        SELECT reason, delta FROM ledger
        WHERE account_id = ? AND source_event_id = ?
        """,
        (account_a, f"match:{match_id}:{account_a}:bits"),
    )
    assert len(markers) == 1
    assert markers[0]["delta"] == 0
    assert markers[0]["reason"] == "pvp.daily_cap"

    ratings = _rows(
        app,
        "SELECT account_id, wins, losses FROM ratings ORDER BY account_id",
    )
    assert {row["account_id"] for row in ratings} == {account_a, account_b}
    assert all(row["wins"] + row["losses"] == 1 for row in ratings)


def test_third_match_vs_same_opponent_pays_zero(
    app, client, auth_headers_a, auth_headers_b, account_a, account_b
):
    _adopt(client, auth_headers_a, "patchfox", "Ash")
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")

    first_id, _ = _play_casual(client, auth_headers_a, auth_headers_b, account_b)
    second_id, _ = _play_casual(client, auth_headers_a, auth_headers_b, account_b)
    third_id, third = _play_casual(client, auth_headers_a, auth_headers_b, account_b)

    for match_id in (first_id, second_id):
        paid = _rows(
            app,
            """
            SELECT delta FROM ledger
            WHERE account_id = ? AND source_event_id = ?
            """,
            (account_a, f"match:{match_id}:{account_a}:bits"),
        )
        assert paid and paid[0]["delta"] > 0

    capped = _rows(
        app,
        """
        SELECT reason, delta FROM ledger
        WHERE account_id = ? AND source_event_id = ?
        """,
        (account_a, f"match:{third_id}:{account_a}:bits"),
    )
    assert len(capped) == 1
    assert capped[0]["delta"] == 0
    assert capped[0]["reason"] == "pvp.opponent_daily_cap"

    for receipt in third["replay"]["rewards"]:
        assert receipt["amount"] == 0
        assert receipt["reward_reason"] == "pvp.opponent_daily_cap"
    assert third["match"]["reward_reason"] == "pvp.opponent_daily_cap"
    assert third["replay"]["reward_reason"] == "pvp.opponent_daily_cap"

    ratings = _rows(
        app,
        "SELECT account_id, wins, losses FROM ratings ORDER BY account_id",
    )
    assert {row["account_id"] for row in ratings} == {account_a, account_b}
    assert all(row["wins"] + row["losses"] == 3 for row in ratings)


def test_wallet_allowances_decrement_with_activity(
    client, auth_headers_a, auth_headers_b, account_b, validate_contract
):
    pet = _adopt(client, auth_headers_a)
    _adopt(client, auth_headers_b, "nullgeist", "Wisp")

    initial = _wallet(client, auth_headers_a)
    validate_contract("Wallet", initial)
    assert initial["allowances"] == {
        "practice_daily_remaining": 3,
        "practice_weekly_bits_remaining": 750,
        "pvp_daily_remaining": 10,
    }

    _practice(client, auth_headers_a, pet["id"])
    after_one = _wallet(client, auth_headers_a)
    assert after_one["allowances"]["practice_daily_remaining"] == 2
    assert after_one["allowances"]["practice_weekly_bits_remaining"] == 700

    _practice(client, auth_headers_a, pet["id"])
    _practice(client, auth_headers_a, pet["id"])
    after_three = _wallet(client, auth_headers_a)
    assert after_three["allowances"]["practice_daily_remaining"] == 0
    assert after_three["allowances"]["practice_weekly_bits_remaining"] == 600

    _practice(client, auth_headers_a, pet["id"])
    after_capped = _wallet(client, auth_headers_a)
    assert after_capped["allowances"]["practice_daily_remaining"] == 0
    assert after_capped["allowances"]["practice_weekly_bits_remaining"] == 600

    _play_casual(client, auth_headers_a, auth_headers_b, account_b)
    after_pvp = _wallet(client, auth_headers_a)
    assert after_pvp["allowances"]["pvp_daily_remaining"] == 9
    validate_contract("Wallet", after_pvp)
