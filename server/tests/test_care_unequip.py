"""Care and unequip contract tests (HGT-W8-S)."""

from __future__ import annotations

import json

from server.app.db import connect

CROWN = "hat.binary_crown"


def _adopt(client, headers, species="byteblob", name="Bit"):
    response = client.post(
        "/v1/pets", headers=headers, json={"species": species, "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _care(client, headers, pet_id, action, key, use_body_key=True):
    body = {"action": action}
    if key is not None and use_body_key:
        body["idempotency_key"] = key
    headers = dict(headers)
    if key is not None and not use_body_key:
        headers["Idempotency-Key"] = key
    return client.post(f"/v1/pets/{pet_id}/care", headers=headers, json=body)


def _rows(app, sql, params=()):
    conn = connect(app.state.db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _set_care(app, pet_id, care):
    conn = connect(app.state.db_path)
    try:
        conn.execute(
            "UPDATE pets SET care_json = ? WHERE id = ?",
            (json.dumps(care, sort_keys=True), pet_id),
        )
        conn.commit()
    finally:
        conn.close()


def _credit(app, account_id, amount, source_event_id):
    from server.app.economy import credit

    conn = connect(app.state.db_path)
    try:
        return credit(conn, account_id, amount, "test.grant", source_event_id)
    finally:
        conn.close()


def _buy_and_equip(client, app, headers, account_id, pet_id, item_id="hat.binary_crown"):
    _credit(app, account_id, 30000, f"seed:{pet_id}")
    bought = client.post(
        "/v1/shop/purchases",
        headers=headers,
        json={"item_id": item_id, "idempotency_key": f"buy:{pet_id}"},
    )
    assert bought.status_code == 201, bought.text
    equipped = client.post(
        f"/v1/pets/{pet_id}/equip",
        headers=headers,
        json={"item_id": item_id, "idempotency_key": f"equip:{pet_id}"},
    )
    assert equipped.status_code == 200, equipped.text
    return equipped.json()


def test_care_requires_authentication(client):
    response = client.post(
        "/v1/pets/00000000-0000-4000-8000-0000000000ff/care",
        json={"action": "feed", "idempotency_key": "no-auth"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_care_requires_idempotency_key(client, auth_headers_a):
    pet = _adopt(client, auth_headers_a)

    response = _care(client, auth_headers_a, pet["id"], "feed", None)

    assert response.status_code == 422
    assert response.json()["code"] == "idempotency_key_required"


def test_care_rejects_unknown_action(client, auth_headers_a):
    pet = _adopt(client, auth_headers_a)

    response = _care(client, auth_headers_a, pet["id"], "hug", "bad-action")

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_care_unknown_pet_is_not_found(client, auth_headers_a):
    response = _care(
        client,
        auth_headers_a,
        "00000000-0000-4000-8000-0000000000ff",
        "feed",
        "missing-pet",
    )

    assert response.status_code == 404
    assert response.json()["code"] == "pet_not_found"


def test_care_rejects_cross_account_ownership(client, auth_headers_a, auth_headers_b):
    pet = _adopt(client, auth_headers_a)

    response = _care(client, auth_headers_b, pet["id"], "feed", "other-account")

    assert response.status_code == 403
    assert response.json()["code"] == "pet_not_owned"
    assert _rows(client.app, "SELECT * FROM care_events") == []


def test_feed_play_and_rest_update_the_expected_meters(
    app, client, auth_headers_a
):
    pet = _adopt(client, auth_headers_a)
    _set_care(
        app,
        pet["id"],
        {"health": 50, "comfort": 40, "hunger": 20, "energy": 30},
    )

    fed = _care(client, auth_headers_a, pet["id"], "feed", "care-feed")
    assert fed.status_code == 200, fed.text
    assert fed.json()["care"]["hunger"] == 45
    assert fed.json()["duplicate"] is False
    assert fed.json()["receipt"]["action"] == "feed"
    assert fed.json()["receipt"]["pet_revision"] == fed.json()["revision"]
    assert fed.json()["pet"]["care"] == fed.json()["care"]

    played = _care(client, auth_headers_a, pet["id"], "play", "care-play")
    assert played.status_code == 200, played.text
    assert played.json()["care"]["comfort"] == 60
    assert played.json()["care"]["energy"] == 20

    rested = _care(client, auth_headers_a, pet["id"], "rest", "care-rest")
    assert rested.status_code == 200, rested.text
    assert rested.json()["care"]["energy"] == 45
    assert rested.json()["revision"] == fed.json()["revision"] + 2


def test_care_meters_clamp_to_zero_and_one_hundred(app, client, auth_headers_a):
    pet = _adopt(client, auth_headers_a)
    _set_care(
        app,
        pet["id"],
        {"health": 100, "comfort": 95, "hunger": 95, "energy": 3},
    )

    fed = _care(client, auth_headers_a, pet["id"], "feed", "clamp-feed")
    assert fed.status_code == 200, fed.text
    assert fed.json()["care"]["hunger"] == 100

    played = _care(client, auth_headers_a, pet["id"], "play", "clamp-play")
    assert played.status_code == 200, played.text
    assert played.json()["care"]["comfort"] == 100
    assert played.json()["care"]["energy"] == 0


def test_care_cooldown_blocks_only_the_same_action(
    app, client, auth_headers_a
):
    pet = _adopt(client, auth_headers_a)

    first = _care(client, auth_headers_a, pet["id"], "feed", "cooldown-1")
    assert first.status_code == 200, first.text

    blocked = _care(client, auth_headers_a, pet["id"], "feed", "cooldown-2")
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["code"] == "care_cooldown"
    assert body["retry_after_s"] > 0
    assert blocked.headers.get("Retry-After")

    other_action = _care(client, auth_headers_a, pet["id"], "rest", "cooldown-3")
    assert other_action.status_code == 200, other_action.text
    assert len(_rows(app, "SELECT * FROM care_events", ())) == 2


def test_care_idempotency_key_replays_the_original_receipt(
    app, client, auth_headers_a
):
    pet = _adopt(client, auth_headers_a)

    first = _care(client, auth_headers_a, pet["id"], "feed", "same-care")
    second = _care(client, auth_headers_a, pet["id"], "feed", "same-care")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    assert second.json()["care"] == first.json()["care"]
    assert second.json()["receipt"]["receipt_id"] == first.json()["receipt"]["receipt_id"]
    assert second.json()["revision"] == first.json()["revision"]
    assert len(_rows(app, "SELECT * FROM care_events", ())) == 1


def test_care_idempotency_key_is_accepted_from_the_header(
    client, auth_headers_a
):
    pet = _adopt(client, auth_headers_a)

    response = _care(
        client, auth_headers_a, pet["id"], "feed", "header-care", use_body_key=False
    )

    assert response.status_code == 200, response.text
    assert response.json()["receipt"]["action"] == "feed"


def test_care_rejects_reused_key_for_a_different_action(
    app, client, auth_headers_a
):
    pet = _adopt(client, auth_headers_a)
    first = _care(client, auth_headers_a, pet["id"], "feed", "reused-care")
    assert first.status_code == 200, first.text

    response = _care(client, auth_headers_a, pet["id"], "play", "reused-care")

    assert response.status_code == 409
    assert response.json()["code"] == "idempotency_conflict"
    assert len(_rows(app, "SELECT * FROM care_events", ())) == 1


def test_unequip_requires_authentication(client):
    response = client.post(
        "/v1/pets/00000000-0000-4000-8000-0000000000ff/unequip",
        json={"slot": "head"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_unequip_unknown_pet_is_not_found(client, auth_headers_a):
    response = client.post(
        "/v1/pets/00000000-0000-4000-8000-0000000000ff/unequip",
        headers=auth_headers_a,
        json={"slot": "head"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "pet_not_found"


def test_unequip_rejects_cross_account_ownership(
    client, auth_headers_a, auth_headers_b
):
    pet = _adopt(client, auth_headers_a)

    response = client.post(
        f"/v1/pets/{pet['id']}/unequip",
        headers=auth_headers_b,
        json={"slot": "head"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "pet_not_owned"


def test_unequip_rejects_invalid_slot(client, auth_headers_a):
    pet = _adopt(client, auth_headers_a)

    response = client.post(
        f"/v1/pets/{pet['id']}/unequip",
        headers=auth_headers_a,
        json={"slot": "hat"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_unequip_removes_the_equipped_item_and_is_idempotent(
    app, client, auth_headers_a, account_a
):
    pet = _adopt(client, auth_headers_a)
    equipped = _buy_and_equip(client, app, auth_headers_a, account_a, pet["id"])
    assert equipped["loadout"]["head"]["id"] == CROWN

    response = client.post(
        f"/v1/pets/{pet['id']}/unequip",
        headers=auth_headers_a,
        json={"slot": "head"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["slot"] == "head"
    assert body["unequipped_item_id"] == CROWN
    assert body["duplicate"] is False
    assert "head" not in body["loadout"]
    assert _rows(app, "SELECT * FROM equipment WHERE pet_id = ?", (pet["id"],)) == []

    repeated = client.post(
        f"/v1/pets/{pet['id']}/unequip",
        headers=auth_headers_a,
        json={"slot": "head"},
    )

    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["duplicate"] is True
    assert repeated.json()["unequipped_item_id"] is None
    assert repeated.json()["loadout"] == {}
