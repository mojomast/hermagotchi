"""Agent chat, DM inbox and taunt contracts (HGT-W13-A).

Every request runs in-process against a temporary SQLite database; no real
network access or private host is used.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from server.app.db import connect, init_db, seed_account
from server.app.social import (
    AgentChatDisabled,
    ChatDailyCap,
    DMBlocked,
    DMCooldown,
    DMUnansweredCap,
    MessageTooLong,
    TauntInvalidMatch,
    dm_channel_for,
    get_chat_settings,
    inbox,
    mark_inbox_read,
    resolve_dm_channel,
    resolve_target_account,
    send_message,
    send_taunt,
    set_agent_chat_enabled,
)
from server.app.social import errors as social_errors

BASE = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
MIGRATION_VERSION = "0013_agent_chat"

ACCOUNT_C = "00000000-0000-4000-8000-0000000000c3"
ACCOUNT_D = "00000000-0000-4000-8000-0000000000d4"


def _conn(app):
    return connect(app.state.db_path)


def _headers(account_id: str) -> dict[str, str]:
    return {"X-Account-Id": account_id}


def _add_pet(conn, account_id, pet_id, name="Pip", species="byteblob"):
    conn.execute(
        """
        INSERT INTO pets (
            id, account_id, species, name, appearance_seed, traits_json,
            stats_json, care_json, care_updated_at, level, xp, created_at, revision
        ) VALUES (?, ?, ?, ?, 'seed', '{}', '{}', '{}', '2026-11-06T00:00:00Z',
                  1, 0, '2026-11-06T00:00:00Z', 1)
        """,
        (pet_id, account_id, species, name),
    )
    conn.commit()


def _add_match(
    conn,
    *,
    challenger,
    defender,
    status="pending",
    winner=None,
    rounds=None,
    final_hp=None,
    resolved_at=None,
):
    challenge_id = str(uuid.uuid4())
    match_id = str(uuid.uuid4())
    created = "2026-11-06T10:00:00.000Z"
    conn.execute(
        """
        INSERT INTO challenges (
            id, challenger_id, defender_id, mode, status, expires_at, created_at
        ) VALUES (?, ?, ?, 'casual', ?, '2026-11-20T10:00:00.000Z', ?)
        """,
        (
            challenge_id,
            challenger,
            defender,
            "resolved" if status == "resolved" else "accepted",
            created,
        ),
    )
    conn.execute(
        """
        INSERT INTO matches (
            id, challenge_id, ruleset_version, economy_version, seed_commitment,
            seed, status, replay_hash, winner, result, rounds, final_hp_json,
            created_at, resolved_at
        ) VALUES (?, ?, 'battle-1', 'economy-1', 'commit', 'seed', ?,
                  ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            match_id,
            challenge_id,
            status,
            "hash" if status == "resolved" else None,
            winner,
            "win" if status == "resolved" else None,
            rounds,
            json.dumps(final_hp) if final_hp is not None else None,
            created,
            resolved_at,
        ),
    )
    conn.commit()
    return match_id


def _enable_agent(conn, account_id):
    set_agent_chat_enabled(conn, account_id, True)


# ---------------------------------------------------------------------------
# Migration and canonical DM naming
# ---------------------------------------------------------------------------


def test_migration_0013_creates_inbox_and_settings_and_rebuilds_chats(tmp_path):
    db_path = init_db(tmp_path / "agent-chat-migration.db")
    conn = connect(db_path)
    try:
        versions = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations")
        }
        assert MIGRATION_VERSION in versions

        chat_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(chats)")
        }
        assert {
            "kind",
            "match_id",
            "match_context_json",
        } <= chat_columns
        assert {
            "account_id",
            "channel_id",
            "last_read_at",
        } == {
            row["name"] for row in conn.execute("PRAGMA table_info(chat_read_cursors)")
        }
        assert {
            "account_id",
            "agent_chat_enabled",
            "updated_at",
        } == {
            row["name"]
            for row in conn.execute("PRAGMA table_info(account_chat_settings)")
        }
        indexes = {
            row["name"] for row in conn.execute("PRAGMA index_list(chats)")
        }
        assert "idx_chats_channel_created" in indexes
        assert "idx_chats_idempotency" in indexes

        seed_account(conn, "00000000-0000-4000-8000-0000000000a1", "alpha")
        long_channel = (
            "dm:00000000-0000-4000-8000-0000000000a1:"
            "00000000-0000-4000-8000-0000000000b2"
        )
        conn.execute(
            """
            INSERT INTO chats (
                id, channel_id, account_id, actor_mode, body, created_at, kind
            ) VALUES (?, ?, ?, 'human', 'long channel', ?, 'chat')
            """,
            (
                str(uuid.uuid4()),
                long_channel,
                "00000000-0000-4000-8000-0000000000a1",
                "2026-11-06T12:00:00.000Z",
            ),
        )
        conn.commit()
        assert len(long_channel) > 64
    finally:
        conn.close()


def test_resolve_dm_channel_is_sorted_and_accepts_id_handle_and_pet(
    app, account_a, account_b
):
    conn = _conn(app)
    try:
        conn.execute(
            "UPDATE accounts SET public_handle = 'bravo_handle' WHERE id = ?",
            (account_b,),
        )
        _add_pet(conn, account_b, "10000000-0000-4000-8000-0000000000b2", "Pip")

        expected = f"dm:{min(account_a, account_b)}:{max(account_a, account_b)}"
        assert dm_channel_for(account_b, account_a) == expected
        assert resolve_dm_channel(conn, account_a, account_b) == expected
        assert resolve_dm_channel(conn, account_a, "bravo_handle") == expected
        assert resolve_dm_channel(conn, account_a, "Pip") == expected
        assert resolve_target_account(conn, "@bravo_handle") == account_b
    finally:
        conn.close()


def test_dm_by_target_ignores_channel_and_prefers_canonical_dm(app, account_a, account_b):
    conn = _conn(app)
    try:
        message = send_message(
            conn,
            "some_channel",
            account_a,
            "hello there",
            target=account_b,
        )
        assert message["channel_id"] == dm_channel_for(account_a, account_b)
        assert message["channel_id"].startswith("dm:")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Blocks, toggle and caps
# ---------------------------------------------------------------------------


def test_dm_blocks_are_respected_in_both_directions(app, account_a, account_b):
    conn = _conn(app)
    try:
        conn.execute(
            "INSERT INTO blocks (blocker_id, blocked_id, created_at) VALUES (?, ?, ?)",
            (account_a, account_b, "2026-11-06T12:00:00.000Z"),
        )
        conn.commit()

        with pytest.raises(DMBlocked) as blocked:
            send_message(conn, None, account_a, "hi", target=account_b)
        assert blocked.value.code == "dm.blocked"

        with pytest.raises(DMBlocked) as reverse_blocked:
            send_message(conn, None, account_b, "hi", target=account_a)
        assert reverse_blocked.value.code == "dm.blocked"
    finally:
        conn.close()


def test_agent_chat_toggle_off_blocks_and_on_allows(app, account_a, account_b):
    conn = _conn(app)
    try:
        with pytest.raises(AgentChatDisabled) as disabled:
            send_message(
                conn, "lobby", account_a, "agent hello", actor_mode="agent", now=BASE
            )
        assert disabled.value.code == "chat.disabled"

        _enable_agent(conn, account_a)
        sent = send_message(
            conn, "lobby", account_a, "agent hello", actor_mode="agent", now=BASE
        )
        assert sent["actor_mode"] == "agent"

        set_agent_chat_enabled(conn, account_a, False, now=BASE)
        assert get_chat_settings(conn, account_a)["agent_chat_enabled"] is False
    finally:
        conn.close()


def test_agent_lobby_daily_cap_is_twenty(app, account_a):
    conn = _conn(app)
    try:
        _enable_agent(conn, account_a)
        for index in range(20):
            send_message(
                conn,
                "lobby",
                account_a,
                f"lobby {index}",
                actor_mode="agent",
                now=BASE + timedelta(seconds=index * 61),
            )
        with pytest.raises(ChatDailyCap) as capped:
            send_message(
                conn,
                "lobby",
                account_a,
                "one too many",
                actor_mode="agent",
                now=BASE + timedelta(seconds=20 * 61),
            )
        assert capped.value.code == "chat.daily_cap"
        assert capped.value.retry_after_s > 0
    finally:
        conn.close()


def test_agent_dm_daily_cap_is_ten_across_recipients(app, account_a):
    conn = _conn(app)
    try:
        _enable_agent(conn, account_a)
        recipients = [
            str(uuid.UUID(f"00000000-0000-4000-8000-{index:012d}"))
            for index in range(1, 12)
        ]
        for recipient in recipients:
            seed_account(conn, recipient, f"dm_target_{recipient[-4:]}")
        for recipient in recipients[:10]:
            send_message(
                conn,
                None,
                account_a,
                "dm hello",
                actor_mode="agent",
                target=recipient,
                now=BASE,
            )
        with pytest.raises(ChatDailyCap) as capped:
            send_message(
                conn,
                None,
                account_a,
                "dm too many",
                actor_mode="agent",
                target=recipients[10],
                now=BASE,
            )
        assert capped.value.code == "chat.daily_cap"
    finally:
        conn.close()


def test_agent_recipient_cooldown_is_sixty_seconds(app, account_a):
    conn = _conn(app)
    try:
        _enable_agent(conn, account_a)
        send_message(conn, "lobby", account_a, "first", actor_mode="agent", now=BASE)
        with pytest.raises(DMCooldown) as cooldown:
            send_message(
                conn, "lobby", account_a, "second", actor_mode="agent", now=BASE
            )
        assert cooldown.value.code == "dm.cooldown"
        assert 0 < cooldown.value.retry_after_s <= 60

        allowed = send_message(
            conn,
            "lobby",
            account_a,
            "third",
            actor_mode="agent",
            now=BASE + timedelta(seconds=61),
        )
        assert allowed["body"] == "third"
    finally:
        conn.close()


def test_agent_unanswered_dm_cap_requires_a_reply(app, account_a, account_b):
    conn = _conn(app)
    try:
        _enable_agent(conn, account_a)
        channel = dm_channel_for(account_a, account_b)
        send_message(
            conn, channel, account_a, "one", actor_mode="agent", now=BASE
        )
        send_message(
            conn,
            channel,
            account_a,
            "two",
            actor_mode="agent",
            now=BASE + timedelta(seconds=61),
        )
        with pytest.raises(DMUnansweredCap) as capped:
            send_message(
                conn,
                channel,
                account_a,
                "three",
                actor_mode="agent",
                now=BASE + timedelta(seconds=122),
            )
        assert capped.value.code == "dm.unanswered_cap"

        send_message(
            conn,
            channel,
            account_b,
            "reply",
            actor_mode="human",
            now=BASE + timedelta(seconds=130),
        )
        allowed = send_message(
            conn,
            channel,
            account_a,
            "after reply",
            actor_mode="agent",
            now=BASE + timedelta(seconds=200),
        )
        assert allowed["body"] == "after reply"
    finally:
        conn.close()


def test_human_rate_limit_is_unchanged(app, account_a):
    conn = _conn(app)
    try:
        for index in range(5):
            send_message(
                conn,
                "lobby",
                account_a,
                f"human {index}",
                actor_mode="human",
                now=BASE + timedelta(milliseconds=index),
            )
        with pytest.raises(social_errors.RateLimited) as limited:
            send_message(
                conn,
                "lobby",
                account_a,
                "too many",
                actor_mode="human",
                now=BASE + timedelta(seconds=1),
            )
        assert limited.value.code == "rate_limited"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Taunts
# ---------------------------------------------------------------------------


def test_taunt_pre_pending_match_posts_to_lobby_with_null_context(app, account_a, account_b):
    conn = _conn(app)
    try:
        match_id = _add_match(conn, challenger=account_a, defender=account_b)
        message = send_taunt(
            conn,
            account_a,
            match_id,
            "good luck!",
            phase="pre",
            lobby=True,
            actor_mode="human",
            now=BASE,
        )
        assert message["kind"] == "taunt"
        assert message["match_id"] == match_id
        assert message["channel_id"] == "lobby"
        assert message["match_context"] == {
            "winner": None,
            "final_hp": None,
            "rounds": None,
        }
    finally:
        conn.close()


def test_taunt_post_finished_match_attaches_context(app, account_a, account_b):
    conn = _conn(app)
    try:
        resolved = (BASE - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        match_id = _add_match(
            conn,
            challenger=account_a,
            defender=account_b,
            status="resolved",
            winner="a",
            rounds=3,
            final_hp={"a": 12, "b": 0},
            resolved_at=resolved,
        )
        message = send_taunt(
            conn,
            account_b,
            match_id,
            "rematch when?",
            phase="post",
            lobby=True,
            actor_mode="human",
            now=BASE,
        )
        assert message["kind"] == "taunt"
        assert message["match_context"] == {
            "winner": "a",
            "final_hp": {"a": 12, "b": 0},
            "rounds": 3,
        }
    finally:
        conn.close()


def test_taunt_rejects_invalid_match_phase_and_non_participant(app, account_a, account_b):
    conn = _conn(app)
    try:
        pending = _add_match(conn, challenger=account_a, defender=account_b)
        with pytest.raises(TauntInvalidMatch) as pending_post:
            send_taunt(
                conn,
                account_a,
                pending,
                "too early",
                phase="post",
                actor_mode="human",
                now=BASE,
            )
        assert pending_post.value.code == "taunt.invalid_match"

        old = (BASE - timedelta(hours=25)).isoformat().replace("+00:00", "Z")
        finished = _add_match(
            conn,
            challenger=account_a,
            defender=account_b,
            status="resolved",
            winner="b",
            rounds=2,
            final_hp={"a": 0, "b": 8},
            resolved_at=old,
        )
        with pytest.raises(TauntInvalidMatch) as expired:
            send_taunt(
                conn,
                account_a,
                finished,
                "old news",
                phase="post",
                actor_mode="human",
                now=BASE,
            )
        assert expired.value.code == "taunt.invalid_match"

        seed_account(conn, ACCOUNT_C, "charlie")
        with pytest.raises(TauntInvalidMatch) as outsider:
            send_taunt(
                conn,
                ACCOUNT_C,
                pending,
                "not mine",
                phase="pre",
                actor_mode="human",
                now=BASE,
            )
        assert outsider.value.code == "taunt.invalid_match"

        with pytest.raises(TauntInvalidMatch) as missing:
            send_taunt(
                conn,
                account_a,
                str(uuid.uuid4()),
                "no match",
                phase="pre",
                actor_mode="human",
                now=BASE,
            )
        assert missing.value.code == "taunt.invalid_match"
    finally:
        conn.close()


def test_taunt_dm_uses_canonical_channel_and_respects_blocks(app, account_a, account_b):
    conn = _conn(app)
    try:
        match_id = _add_match(conn, challenger=account_a, defender=account_b)
        message = send_taunt(
            conn,
            account_a,
            match_id,
            "see you there",
            phase="pre",
            lobby=False,
            actor_mode="human",
            now=BASE,
        )
        assert message["channel_id"] == dm_channel_for(account_a, account_b)

        conn.execute(
            "INSERT INTO blocks (blocker_id, blocked_id, created_at) VALUES (?, ?, ?)",
            (account_b, account_a, "2026-11-06T12:00:00.000Z"),
        )
        conn.commit()
        with pytest.raises(DMBlocked) as blocked:
            send_taunt(
                conn,
                account_a,
                match_id,
                "blocked",
                phase="pre",
                lobby=False,
                actor_mode="human",
                now=BASE + timedelta(seconds=10),
            )
        assert blocked.value.code == "dm.blocked"
    finally:
        conn.close()


def test_taunt_body_and_agent_toggle(app, account_a, account_b):
    conn = _conn(app)
    try:
        match_id = _add_match(conn, challenger=account_a, defender=account_b)
        with pytest.raises(MessageTooLong):
            send_taunt(
                conn,
                account_a,
                match_id,
                "x" * 121,
                phase="pre",
                actor_mode="human",
                now=BASE,
            )

        with pytest.raises(AgentChatDisabled) as disabled:
            send_taunt(
                conn,
                account_a,
                match_id,
                "agent taunt",
                phase="pre",
                actor_mode="agent",
                now=BASE,
            )
        assert disabled.value.code == "chat.disabled"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------


def test_inbox_returns_dms_and_mentions_with_cursor_and_read_marker(
    app, account_a, account_b
):
    conn = _conn(app)
    try:
        conn.execute(
            "UPDATE accounts SET public_handle = 'alpha_handle' WHERE id = ?",
            (account_a,),
        )
        conn.commit()

        dm = send_message(
            conn,
            None,
            account_b,
            "direct hello",
            target=account_a,
            now=BASE,
        )
        mention = send_message(
            conn,
            "lobby",
            account_b,
            "@alpha_handle good game",
            now=BASE + timedelta(seconds=1),
        )
        send_message(
            conn,
            "lobby",
            account_b,
            "@alpha_handle_extra not me",
            now=BASE + timedelta(seconds=2),
        )
        send_message(
            conn,
            "lobby",
            account_b,
            "no mention here",
            now=BASE + timedelta(seconds=3),
        )

        messages, cursor = inbox(conn, account_a)
        assert [item["id"] for item in messages] == [dm["id"], mention["id"]]
        assert cursor

        again, same_cursor = inbox(conn, account_a, cursor=cursor)
        assert again == []
        assert same_cursor == cursor

        marker = mark_inbox_read(conn, account_a, cursor, now=BASE)
        assert marker["last_read_at"] == cursor.split("|", 1)[0]
        after_read, _ = inbox(conn, account_a)
        assert after_read == []
    finally:
        conn.close()


def test_inbox_pagination_and_block_filter(app, account_a, account_b):
    conn = _conn(app)
    try:
        seed_account(conn, ACCOUNT_C, "charlie")
        messages = []
        for index in range(3):
            messages.append(
                send_message(
                    conn,
                    None,
                    account_b,
                    f"dm {index}",
                    target=account_a,
                    now=BASE + timedelta(seconds=index),
                )
            )
        blocked_message = send_message(
            conn,
            None,
            ACCOUNT_C,
            "blocked dm",
            target=account_a,
            now=BASE + timedelta(seconds=5),
        )
        conn.execute(
            "INSERT INTO blocks (blocker_id, blocked_id, created_at) VALUES (?, ?, ?)",
            (account_a, ACCOUNT_C, "2026-11-06T12:00:00.000Z"),
        )
        conn.commit()

        first_page, cursor = inbox(conn, account_a, limit=2)
        assert blocked_message["id"] not in {item["id"] for item in first_page}
        assert [item["id"] for item in first_page] == [messages[0]["id"], messages[1]["id"]]
        second_page, cursor2 = inbox(conn, account_a, cursor=cursor, limit=2)
        assert [item["id"] for item in second_page] == [messages[2]["id"]]
        assert cursor2 != cursor
        rest, _ = inbox(conn, account_a, cursor=cursor2, limit=2)
        assert rest == []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# HTTP routes and live settings projection
# ---------------------------------------------------------------------------


def test_me_projects_live_chat_settings_and_toggle_routes(client, auth_headers_a):
    initial = client.get("/v1/me", headers=auth_headers_a)
    assert initial.status_code == 200
    assert initial.json()["policy"]["chat_enabled"] is False
    assert initial.json()["permissions"]["chat"] is False
    assert initial.json()["chat_settings"]["agent_chat_enabled"] is False

    enabled = client.patch(
        "/v1/me/policy", headers=auth_headers_a, json={"chat_enabled": True}
    )
    assert enabled.status_code == 200, enabled.text
    body = enabled.json()
    assert body["policy"]["chat_enabled"] is True
    assert body["permissions"]["chat"] is True
    assert body["chat_settings"]["agent_chat_enabled"] is True
    assert body["chat_settings"]["updated_at"]

    disabled = client.put(
        "/v1/me/chat-settings",
        headers=auth_headers_a,
        json={"agent_chat_enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["policy"]["chat_enabled"] is False

    missing = client.patch("/v1/me/policy", headers=auth_headers_a, json={})
    assert missing.status_code == 422


def test_http_agent_chat_toggle_off_returns_stable_reason(
    client, auth_headers_a
):
    response = client.post(
        "/v1/chat/channels/lobby/messages",
        headers=auth_headers_a,
        json={"body": "agent hello", "actor_mode": "agent"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "chat.disabled"

    assert client.patch(
        "/v1/me/policy", headers=auth_headers_a, json={"agent_chat_enabled": True}
    ).status_code == 200

    allowed = client.post(
        "/v1/chat/channels/lobby/messages",
        headers=auth_headers_a,
        json={"body": "agent hello", "actor_mode": "agent"},
    )
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["message"]["actor_mode"] == "agent"


def test_http_dm_by_target_and_inbox_routes(
    client, auth_headers_a, auth_headers_b, account_a, account_b, app
):
    conn = _conn(app)
    try:
        conn.execute(
            "UPDATE accounts SET public_handle = 'alpha_route' WHERE id = ?",
            (account_a,),
        )
        conn.commit()
    finally:
        conn.close()

    dm_response = client.post(
        "/v1/chat/channels/lobby/messages",
        headers=auth_headers_b,
        json={"body": "route dm", "target": "alpha_route"},
    )
    assert dm_response.status_code == 201, dm_response.text
    assert dm_response.json()["message"]["channel_id"] == dm_channel_for(
        account_a, account_b
    )

    bodyless_path = client.post(
        "/v1/chat/messages",
        headers=auth_headers_b,
        json={"body": "body target dm", "target": account_a},
    )
    assert bodyless_path.status_code == 201, bodyless_path.text

    mention = client.post(
        "/v1/chat/channels/lobby/messages",
        headers=auth_headers_b,
        json={"body": "@alpha_route hello"},
    )
    assert mention.status_code == 201

    inbox_response = client.get("/v1/chat/inbox", headers=auth_headers_a)
    assert inbox_response.status_code == 200, inbox_response.text
    inbox_body = inbox_response.json()
    bodies = [item["body"] for item in inbox_body["messages"]]
    assert "route dm" in bodies
    assert "body target dm" in bodies
    assert "@alpha_route hello" in bodies
    assert inbox_body["next_cursor"]

    marked = client.post(
        "/v1/chat/inbox/read",
        headers=auth_headers_a,
        json={"cursor": inbox_body["next_cursor"]},
    )
    assert marked.status_code == 200
    assert marked.json()["read_marker"]["last_read_at"]

    empty = client.get("/v1/chat/inbox", headers=auth_headers_a)
    assert empty.json()["messages"] == []


def test_http_taunt_pre_and_post_routes(
    client, auth_headers_a, account_a, account_b, app
):
    conn = _conn(app)
    try:
        pending = _add_match(conn, challenger=account_a, defender=account_b)
        resolved_at = (BASE - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        finished = _add_match(
            conn,
            challenger=account_a,
            defender=account_b,
            status="resolved",
            winner="a",
            rounds=4,
            final_hp={"a": 9, "b": 0},
            resolved_at=resolved_at,
        )
    finally:
        conn.close()

    pre = client.post(
        "/v1/chat/taunt",
        headers=auth_headers_a,
        json={
            "match_id": pending,
            "body": "queued and ready",
            "phase": "pre",
            "lobby": True,
            "actor_mode": "human",
        },
    )
    assert pre.status_code == 201, pre.text
    assert pre.json()["message"]["kind"] == "taunt"

    post = client.post(
        "/v1/chat/taunt",
        headers=auth_headers_a,
        json={
            "match_id": finished,
            "body": "good battle",
            "phase": "post",
            "lobby": True,
            "actor_mode": "human",
        },
    )
    assert post.status_code == 201, post.text
    context = post.json()["message"]["match_context"]
    assert context == {"winner": "a", "final_hp": {"a": 9, "b": 0}, "rounds": 4}

    invalid = client.post(
        "/v1/chat/taunt",
        headers=auth_headers_a,
        json={
            "match_id": finished,
            "body": "too soon",
            "phase": "pre",
            "actor_mode": "human",
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "taunt.invalid_match"


def test_http_taunt_agent_default_requires_toggle(
    client, auth_headers_a, account_a, account_b, app
):
    conn = _conn(app)
    try:
        match_id = _add_match(conn, challenger=account_a, defender=account_b)
    finally:
        conn.close()

    disabled = client.post(
        "/v1/chat/taunt",
        headers=auth_headers_a,
        json={"match_id": match_id, "body": "gg", "phase": "pre"},
    )
    assert disabled.status_code == 403
    assert disabled.json()["code"] == "chat.disabled"

    client.patch(
        "/v1/me/policy", headers=auth_headers_a, json={"agent_chat_enabled": True}
    )
    allowed = client.post(
        "/v1/chat/taunt",
        headers=auth_headers_a,
        json={"match_id": match_id, "body": "gg", "phase": "pre"},
    )
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["message"]["actor_mode"] == "agent"
