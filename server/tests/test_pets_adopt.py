"""Adopt-once and public pet sanitisation tests (HGT-W1-A)."""

from __future__ import annotations

import uuid

import pytest


def _adopt(client, headers, **overrides):
    payload = {"species": "byteblob", "name": "Nibbles"}
    payload.update(overrides)
    return client.post("/v1/pets", headers=headers, json=payload)


def test_adopt_creates_private_pet_for_owner(client, auth_headers_a, account_a, validate_contract):
    response = _adopt(client, auth_headers_a)

    assert response.status_code == 201
    body = response.json()
    validate_contract("PetPrivate", body)
    assert body["contracts_version"] == "contracts-v1"
    assert str(uuid.UUID(body["id"])) == body["id"]
    assert body["account_id"] == account_a
    assert body["species"] == "byteblob"
    assert body["name"] == "Nibbles"
    assert body["level"] == 1
    assert body["xp"] == 0
    assert body["revision"] == 1
    assert body["care"] == {"health": 100, "comfort": 100, "hunger": 100, "energy": 100}
    assert body["appearance"]["species"] == "byteblob"
    assert body["appearance_seed"] == body["appearance"]["seed"]
    assert body["appearance"]["seed"]
    assert body["appearance"]["asset_pack_version"] == "launch-003"
    assert body["care_updated_at"].endswith("Z")


def test_adopt_requires_authentication(client):
    response = client.post("/v1/pets", json={"species": "patchfox"})

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_adopt_is_once_per_account(client, auth_headers_a):
    first = _adopt(client, auth_headers_a)
    second = _adopt(client, auth_headers_a, species="patchfox", name="Second")

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["code"] == "pet_already_adopted"
    assert second.json()["correlation_id"]


def test_two_accounts_each_adopt_once(client, auth_headers_a, auth_headers_b):
    pet_a = _adopt(client, auth_headers_a, species="patchfox")
    pet_b = _adopt(client, auth_headers_b, species="nullgeist", name="Wisp")

    assert pet_a.status_code == 201
    assert pet_b.status_code == 201
    assert pet_a.json()["id"] != pet_b.json()["id"]


@pytest.mark.parametrize(
    "species",
    [
        "byteblob",
        "patchfox",
        "nullgeist",
        "kernelcrab",
        "cachebat",
        "stacktoise",
        "daemowl",
        "shellsnail",
        "regexopus",
        "firewyrm",
    ],
)
def test_all_ten_species_are_adoptable(client, auth_headers_a, species):
    response = _adopt(client, auth_headers_a, species=species)

    assert response.status_code == 201
    assert response.json()["species"] == species


@pytest.mark.parametrize("species", ["dragon", "", None])
def test_unknown_species_is_rejected(client, auth_headers_a, species):
    response = _adopt(client, auth_headers_a, species=species)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["correlation_id"]


def test_appearance_seed_is_server_side_and_stable(client, auth_headers_a):
    first = _adopt(client, auth_headers_a, appearance_seed="client-chosen-seed")
    assert first.status_code == 201
    seed = first.json()["appearance"]["seed"]
    assert seed != "client-chosen-seed"

    pet_id = first.json()["id"]
    public = client.get(f"/v1/pets/{pet_id}")
    assert public.status_code == 200
    assert public.json()["appearance"]["seed"] == seed


def test_get_pet_public_payload_is_sanitized(
    client, auth_headers_a, account_a, validate_contract
):
    adopted = _adopt(client, auth_headers_a).json()

    response = client.get(f"/v1/pets/{adopted['id']}")

    assert response.status_code == 200
    public = response.json()
    validate_contract("PetPublic", public)
    assert public["id"] == adopted["id"]
    assert public["contracts_version"] == "contracts-v1"
    assert "account_id" not in public
    assert "care_updated_at" not in public
    assert "appearance_seed" not in public
    assert account_a not in str(public)
    assert public["appearance"]["seed"] == adopted["appearance"]["seed"]
    assert public["care"] == adopted["care"]


def test_get_unknown_pet_returns_not_found(client):
    response = client.get("/v1/pets/00000000-0000-4000-8000-0000000000ff")

    assert response.status_code == 404
    assert response.json()["code"] == "pet_not_found"


def test_get_pet_rejects_malformed_id(client):
    response = client.get("/v1/pets/not-a-uuid")

    assert response.status_code == 404
    assert response.json()["code"] == "pet_not_found"
