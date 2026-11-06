"""Friends, presence and social history contracts (HGT-W14-A).

Every test runs in-process against a temporary SQLite database. No network
access is used and no private host or path is printed.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from server.app.db import connect, init_db, seed_account
from server.app.social import (
    FriendAlready,
    FriendBlocked,
    FriendNotFound,
    FriendPending,
    FriendSelf,
    InvalidHistoryFilter,
    InvalidTarget,
    accept_friend_request,
    decline_friend_request,
    get_presence,
    list_friend_requests,
    list_friends,
    list_social_history,
    presence_bucket,
    remove_friend,
    respond_friend_request,
    send_friend_request,
    touch_presence,
)

BASE = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
MIGRATION_VERSION = "0014_friends_presence"
ACCOUNT_C = "00000000-0000-4000-8000-0000000000c3"


def _conn(app):
    return connect(app.state.db_path)


def _add_match(conn, challenger, defender, *, created="2026-11-06T10:00:00.000Z"):
    challenge_id = str(uuid.uuid4())
    match_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO challenges (
            id, challenger_id, defender_id, mode, status, expires_at, created_at
        ) VALUES (?, ?, ?, 'casual', 'accepted', '2026-11-20T10:00:00.000Z', ?)
        """,
        (challenge_id, challenger, defender, created),
    )
    conn.execute(
        """
        INSERT INTO matches (
            id, challenge_id, ruleset_version, economy_version, seed_commitment,
            seed, status, replay_hash, winner, result, rounds, final_hp_json,
            created_at, resolved_at
        ) VALUES (?, ?, 'battle-1', 'economy-1', 'commit', 'seed', 'pending',
                  NULL, NULL, NULL, NULL, NULL, ?, NULL)
        """,
        (match_id, challenge_id, created),
    )
    conn.commit()
    return match_id


def _add_chat(
    conn,
    account_id,
    body,
    *,
    kind="chat",
    match_id=None,
    channel="lobby",
    created="2026-11-06T10:00:00.000Z",
):
    message_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO chats (
            id, channel_id, account_id, actor_mode, body, idempotency_key,
            created_at, deleted_at, kind, match_id, match_context_json
        ) VALUES (?, ?, ?, 'human', ?, NULL, ?, NULL, ?, ?, NULL)
        """,
        (message_id, channel, account_id, body, created, kind, match_id),
    )
    conn.commit()
    return message_id


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def test_migration_0014_creates_friend_tables_and_pending_index(tmp_path):
    db_path = init_db(tmp_path / "friends-migration.db")
    conn = connect(db_path)
    try:
        versions = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations")
        }
        assert MIGRATION_VERSION in versions

        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"friend_requests", "friendships", "account_presence"} <= tables

        assert {
            "id",
            "from_account_id",
            "to_account_id",
            "status",
            "created_at",
            "resolved_at",
        } == {
            row["name"]
            for row in conn.execute("PRAGMA table_info(friend_requests)")
        }
        assert {"account_id", "friend_id", "created_at"} == {
            row["name"] for row in conn.execute("PRAGMA table_info(friendships)")
        }
        assert {"account_id", "last_seen_at"} == {
            row["name"] for row in conn.execute("PRAGMA table_info(account_presence)")
        }

        indexes = {
            row["name"]
            for row in conn.execute("PRAGMA index_list(friend_requests)")
        }
        assert "idx_friend_requests_pending_pair" in indexes

        account_a = "00000000-0000-4000-8000-0000000000a1"
        account_b = "00000000-0000-4000-8000-0000000000b2"
        seed_account(conn, account_a, "alpha")
        seed_account(conn, account_b, "bravo")
        conn.execute(
            """
            INSERT INTO friend_requests (
                id, from_account_id, to_account_id, status, created_at
            ) VALUES (?, ?, ?, 'pending', ?)
            """,
            (str(uuid.uuid4()), account_a, account_b, "2026-11-06T12:00:00.000Z"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO friend_requests (
                    id, from_account_id, to_account_id, status, created_at
                ) VALUES (?, ?, ?, 'pending', ?)
                """,
                (
                    str(uuid.uuid4()),
                    account_a,
                    account_b,
                    "2026-11-06T12:01:00.000Z",
                ),
            )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Requests, acceptance and removal
# ---------------------------------------------------------------------------


def test_friend_request_accept_remove_lifecycle(app, account_a, account_b):
    conn = _conn(app)
    try:
        request = send_friend_request(conn, account_a, account_b, now=BASE)
        assert request["status"] == "pending"
        assert request["resolved_at"] is None
        assert request["from_account_id"] == account_a
        assert request["to_account_id"] == account_b

        with pytest.raises(FriendPending) as duplicate:
            send_friend_request(conn, account_a, account_b, now=BASE)
        assert duplicate.value.code == "friend.pending"

        with pytest.raises(FriendPending):
            send_friend_request(conn, account_b, account_a, now=BASE)

        accepted = respond_friend_request(
            conn, account_b, request["id"], "accept", now=BASE + timedelta(seconds=1)
        )
        assert accepted["status"] == "accepted"
        assert accepted["resolved_at"] is not None

        both = conn.execute(
            "SELECT COUNT(*) AS n FROM friendships WHERE account_id IN (?, ?)",
            (account_a, account_b),
        ).fetchone()
        assert both["n"] == 2

        friends = list_friends(conn, account_a, now=BASE)
        assert [friend["friend_id"] for friend in friends] == [account_b]
        assert friends[0]["presence"] == "offline"

        with pytest.raises(FriendAlready) as already:
            send_friend_request(conn, account_b, account_a, now=BASE)
        assert already.value.code == "friend.already"

        with pytest.raises(FriendAlready):
            respond_friend_request(conn, account_b, request["id"], "accept", now=BASE)

        removed = remove_friend(conn, account_a, account_b)
        assert removed["removed"] is True
        remaining = conn.execute(
            "SELECT COUNT(*) AS n FROM friendships"
        ).fetchone()
        assert remaining["n"] == 0

        with pytest.raises(FriendNotFound) as missing:
            remove_friend(conn, account_a, account_b)
        assert missing.value.code == "friend.not_found"
    finally:
        conn.close()


def test_friend_request_refuses_self_missing_and_nonrecipient(
    app, account_a, account_b
):
    conn = _conn(app)
    try:
        with pytest.raises(FriendSelf) as own:
            send_friend_request(conn, account_a, account_a)
        assert own.value.code == "friend.self"

        with pytest.raises(FriendNotFound) as missing:
            send_friend_request(conn, account_a, str(uuid.uuid4()))
        assert missing.value.code == "friend.not_found"

        request = send_friend_request(conn, account_a, account_b, now=BASE)
        with pytest.raises(FriendNotFound):
            respond_friend_request(conn, account_a, request["id"], "accept")
        with pytest.raises(FriendNotFound):
            respond_friend_request(conn, account_b, str(uuid.uuid4()), "accept")
        with pytest.raises(InvalidTarget):
            respond_friend_request(conn, account_b, request["id"], "sideways")
    finally:
        conn.close()


def test_decline_keeps_them_unfriended_and_allows_new_request(
    app, account_a, account_b
):
    conn = _conn(app)
    try:
        request = send_friend_request(conn, account_a, account_b, now=BASE)
        declined = decline_friend_request(
            conn, account_b, request["id"], now=BASE + timedelta(seconds=2)
        )
        assert declined["status"] == "declined"
        assert declined["resolved_at"] is not None
        assert list_friends(conn, account_a) == []
        assert list_friends(conn, account_b) == []

        retry = send_friend_request(
            conn, account_a, account_b, now=BASE + timedelta(seconds=3)
        )
        assert retry["id"] != request["id"]
        assert retry["status"] == "pending"

        outgoing = list_friend_requests(conn, account_a)["outgoing"]
        assert [item["id"] for item in outgoing] == [retry["id"]]
        incoming = list_friend_requests(conn, account_b)["incoming"]
        assert [item["id"] for item in incoming] == [retry["id"]]
    finally:
        conn.close()


def test_blocks_refuse_requests_and_acceptance_both_ways(app, account_a, account_b):
    conn = _conn(app)
    try:
        conn.execute(
            "INSERT INTO blocks (blocker_id, blocked_id, created_at) VALUES (?, ?, ?)",
            (account_a, account_b, "2026-11-06T12:00:00.000Z"),
        )
        conn.commit()

        with pytest.raises(FriendBlocked) as forward:
            send_friend_request(conn, account_a, account_b)
        assert forward.value.code == "friend.blocked"

        with pytest.raises(FriendBlocked):
            send_friend_request(conn, account_b, account_a)

        conn.execute(
            "DELETE FROM blocks WHERE blocker_id = ? AND blocked_id = ?",
            (account_a, account_b),
        )
        conn.commit()
        request = send_friend_request(conn, account_a, account_b, now=BASE)

        conn.execute(
            "INSERT INTO blocks (blocker_id, blocked_id, created_at) VALUES (?, ?, ?)",
            (account_b, account_a, "2026-11-06T12:01:00.000Z"),
        )
        conn.commit()
        with pytest.raises(FriendBlocked):
            accept_friend_request(conn, account_b, request["id"])
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Presence
# ---------------------------------------------------------------------------


def test_presence_buckets_follow_utc_windows(app, account_a, account_b):
    conn = _conn(app)
    try:
        request = send_friend_request(conn, account_a, account_b, now=BASE)
        accept_friend_request(conn, account_b, request["id"], now=BASE)

        touch_presence(conn, account_b, now=BASE)
        assert get_presence(conn, account_b, now=BASE)["presence"] == "online"
        assert (
            list_friends(conn, account_a, now=BASE + timedelta(seconds=119))[0][
                "presence"
            ]
            == "online"
        )
        assert (
            list_friends(conn, account_a, now=BASE + timedelta(seconds=120))[0][
                "presence"
            ]
            == "away"
        )
        assert (
            list_friends(conn, account_a, now=BASE + timedelta(seconds=899))[0][
                "presence"
            ]
            == "away"
        )
        assert (
            list_friends(conn, account_a, now=BASE + timedelta(seconds=900))[0][
                "presence"
            ]
            == "offline"
        )

        touch_presence(conn, account_b, now=BASE + timedelta(seconds=901))
        refreshed = list_friends(conn, account_a, now=BASE + timedelta(seconds=902))
        assert refreshed[0]["presence"] == "online"

        assert presence_bucket(None) == "offline"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def test_friend_and_presence_routes(
    client, app, account_a, account_b, auth_headers_a, auth_headers_b
):
    response = client.post(
        "/v1/friends", headers=auth_headers_a, json={"account_id": account_b}
    )
    assert response.status_code == 201
    request = response.json()["request"]
    assert request["to_account_id"] == account_b

    outgoing = client.get("/v1/friends", headers=auth_headers_a).json()
    assert [item["id"] for item in outgoing["outgoing_requests"]] == [request["id"]]
    incoming = client.get("/v1/friends", headers=auth_headers_b).json()
    assert [item["id"] for item in incoming["incoming_requests"]] == [request["id"]]

    accepted = client.post(
        f"/v1/friends/requests/{request['id']}/respond",
        headers=auth_headers_b,
        json={"action": "accept"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["request"]["status"] == "accepted"

    listed = client.get("/v1/friends", headers=auth_headers_a).json()
    assert [friend["friend_id"] for friend in listed["friends"]] == [account_b]
    assert listed["friends"][0]["presence"] == "online"

    presence = client.post("/v1/presence", headers=auth_headers_b)
    assert presence.status_code == 200
    assert presence.json()["presence"]["presence"] == "online"

    self_request = client.post(
        "/v1/friends", headers=auth_headers_a, json={"account_id": account_a}
    )
    assert self_request.status_code == 422
    assert self_request.json()["code"] == "friend.self"

    removed = client.delete(f"/v1/friends/{account_b}", headers=auth_headers_a)
    assert removed.status_code == 200
    assert removed.json()["removed"] is True

    missing = client.delete(f"/v1/friends/{account_b}", headers=auth_headers_a)
    assert missing.status_code == 404
    assert missing.json()["code"] == "friend.not_found"


# ---------------------------------------------------------------------------
# Social history
# ---------------------------------------------------------------------------


def _seed_history(app, account_a, account_b):
    conn = _conn(app)
    try:
        seed_account(conn, ACCOUNT_C, "charlie")
        conn.execute(
            "UPDATE accounts SET public_handle = 'alpha' WHERE id = ?",
            (account_a,),
        )
        conn.execute(
            "UPDATE accounts SET public_handle = 'bravo' WHERE id = ?",
            (account_b,),
        )
        conn.commit()

        related = _add_match(conn, account_a, account_b)
        unrelated = _add_match(conn, account_b, ACCOUNT_C)

        _add_chat(
            conn,
            account_a,
            "sent taunt",
            kind="taunt",
            match_id=related,
            created="2026-11-06T10:00:00.000Z",
        )
        _add_chat(
            conn,
            account_b,
            "received taunt",
            kind="taunt",
            match_id=related,
            created="2026-11-06T10:01:00.000Z",
        )
        _add_chat(
            conn,
            account_b,
            "unrelated taunt",
            kind="taunt",
            match_id=unrelated,
            created="2026-11-06T10:02:00.000Z",
        )
        _add_chat(
            conn,
            account_b,
            "hey @alpha look",
            created="2026-11-06T10:03:00.000Z",
        )
        _add_chat(
            conn,
            account_a,
            "self @alpha mention",
            created="2026-11-06T10:04:00.000Z",
        )
        _add_chat(
            conn,
            account_b,
            "plain chat",
            created="2026-11-06T10:05:00.000Z",
        )
        return related
    finally:
        conn.close()


def test_social_history_filters_and_match_ids(app, account_a, account_b):
    related = _seed_history(app, account_a, account_b)
    conn = _conn(app)
    try:
        sent, _ = list_social_history(conn, account_a, filter="taunts_sent")
        assert len(sent) == 1
        assert sent[0]["body"] == "sent taunt"
        assert sent[0]["match_id"] == related

        received, _ = list_social_history(conn, account_a, filter="taunts_received")
        assert len(received) == 1
        assert received[0]["body"] == "received taunt"
        assert received[0]["match_id"] == related

        mentions, _ = list_social_history(conn, account_a, filter="mentions")
        assert len(mentions) == 1
        assert mentions[0]["body"] == "hey @alpha look"
        assert mentions[0].get("match_id") is None

        everything, next_before = list_social_history(conn, account_a, filter="all")
        assert {entry["body"] for entry in everything} == {
            "sent taunt",
            "received taunt",
            "hey @alpha look",
        }
        assert next_before is None
        assert len({entry["id"] for entry in everything}) == 3

        page, cursor = list_social_history(conn, account_a, filter="all", limit=2)
        assert len(page) == 2
        assert cursor == page[-1]["created_at"]

        with pytest.raises(InvalidHistoryFilter):
            list_social_history(conn, account_a, filter="everything")
    finally:
        conn.close()


def test_social_history_route(
    client, app, account_a, account_b, auth_headers_a
):
    related = _seed_history(app, account_a, account_b)

    response = client.get(
        "/v1/social/history",
        headers=auth_headers_a,
        params={"filter": "taunts_received"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["filter"] == "taunts_received"
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["match_id"] == related

    invalid = client.get(
        "/v1/social/history",
        headers=auth_headers_a,
        params={"filter": "everything"},
    )
    assert invalid.status_code == 422
