"""Shared pytest fixtures for the Hermagotchi server contract tests."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ACCOUNT_A = str(uuid.UUID("00000000-0000-4000-8000-0000000000a1"))
ACCOUNT_B = str(uuid.UUID("00000000-0000-4000-8000-0000000000b2"))


@pytest.fixture
def account_a() -> str:
    return ACCOUNT_A


@pytest.fixture
def account_b() -> str:
    return ACCOUNT_B


@pytest.fixture
def auth_headers_a(account_a: str) -> dict[str, str]:
    return {"X-Account-Id": account_a}


@pytest.fixture
def auth_headers_b(account_b: str) -> dict[str, str]:
    return {"X-Account-Id": account_b}


@pytest.fixture(scope="session")
def validate_contract():
    schema_dir = REPO_ROOT / "shared" / "schema"
    manifest = json.loads((schema_dir / "manifest.json").read_text(encoding="utf-8"))
    schemas = {
        name: json.loads((schema_dir / entry["schema"]).read_text(encoding="utf-8"))
        for name, entry in manifest["schemas"].items()
    }
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )

    def _validate(name: str, payload: dict) -> None:
        Draft202012Validator(schemas[name], registry=registry).validate(payload)

    return _validate


@pytest.fixture
def app(tmp_path: Path, account_a: str, account_b: str):
    from server.app.main import create_app

    return create_app(
        db_path=tmp_path / "hermagotchi-test.db",
        seed_account_ids=(account_a, account_b),
    )


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
