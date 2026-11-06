"""Health, identity and frozen-schema smoke tests (HGT-W1-A)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "shared" / "schema"

CONTRACT_NAMES = {
    "PetPublic",
    "PetPrivate",
    "Appearance",
    "Item",
    "Wallet",
    "LedgerEntry",
    "Challenge",
    "TacticCard",
    "Match",
    "ReplayEvent",
    "ChatMessage",
    "Goal",
    "Policy",
    "ApiError",
    "GameEvent",
    "AssetManifest",
}


def test_healthz_returns_ok(client):
    response = client.get("/v1/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "hermagotchi",
        "contracts_version": "contracts-v1",
    }


def test_me_requires_authentication(client):
    response = client.get("/v1/me")

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "unauthorized"
    assert body["retry_after_s"] == 0
    assert body["correlation_id"]


def test_me_returns_account_and_default_policy(
    client, auth_headers_a, account_a, validate_contract
):
    response = client.get("/v1/me", headers=auth_headers_a)

    assert response.status_code == 200
    body = response.json()
    assert body["account"]["id"] == account_a
    assert body["account"]["status"] == "active"
    assert body["contracts_version"] == "contracts-v1"
    policy = body["policy"]
    assert policy["mode"] == "human"
    assert policy["network_enabled"] is False
    assert policy["autonomy_enabled"] is False
    assert policy["chat_enabled"] is False
    validate_contract("Policy", policy)


def test_me_unknown_account_is_rejected(client, auth_headers_a):
    headers = {"X-Account-Id": "00000000-0000-4000-8000-00000000dead"}
    response = client.get("/v1/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_contracts_v1_manifest_and_fixtures_validate():
    manifest = json.loads((SCHEMA_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["contracts_version"] == "contracts-v1"
    assert manifest["economy_version"] == "economy-1"
    assert manifest["ruleset_version"] == "battle-1"
    assert set(manifest["schemas"]) == CONTRACT_NAMES

    resources = []
    for entry in manifest["schemas"].values():
        schema = json.loads((SCHEMA_DIR / entry["schema"]).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        resources.append((schema["$id"], Resource.from_contents(schema)))

    registry = Registry().with_resources(resources)

    for name, entry in manifest["schemas"].items():
        schema = json.loads((SCHEMA_DIR / entry["schema"]).read_text(encoding="utf-8"))
        fixture = json.loads((SCHEMA_DIR / entry["fixture"]).read_text(encoding="utf-8"))

        assert schema["title"] == name
        validator = Draft202012Validator(schema, registry=registry)
        validator.validate(fixture)


@pytest.mark.parametrize(
    "mutator",
    [
        pytest.param(lambda fixture: fixture.update({"contracts_version": "v2"}), id="bad-contracts-version"),
        pytest.param(lambda fixture: fixture.pop("appearance"), id="missing-appearance"),
    ],
)
def test_public_pet_fixture_rejects_bad_contract_shape(mutator):
    manifest = json.loads((SCHEMA_DIR / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["schemas"]["PetPublic"]
    schema = json.loads((SCHEMA_DIR / entry["schema"]).read_text(encoding="utf-8"))
    fixture = json.loads((SCHEMA_DIR / entry["fixture"]).read_text(encoding="utf-8"))
    fixture["id"] = "00000000-0000-4000-8000-0000000000c3"

    resources = []
    for other in manifest["schemas"].values():
        other_schema = json.loads((SCHEMA_DIR / other["schema"]).read_text(encoding="utf-8"))
        resources.append((other_schema["$id"], Resource.from_contents(other_schema)))
    registry = Registry().with_resources(resources)

    mutator(fixture)
    validator = Draft202012Validator(schema, registry=registry)

    assert not validator.is_valid(fixture)
