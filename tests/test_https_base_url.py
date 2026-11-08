"""Game API base URLs must be HTTPS except loopback (catalog review, recommended item)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_client.auth import PairingClient  # noqa: E402
from game_client.client import GameClient, require_secure_url  # noqa: E402
from game_client.errors import GameClientError  # noqa: E402


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com/v1",
        "https://api.example.com",
        "http://127.0.0.1:8000/v1",
        "http://127.5.6.7/v1",
        "http://localhost:8000",
        "http://[::1]:8000/v1",
    ],
)
def test_allows_https_and_loopback_http(url: str) -> None:
    client = GameClient(base_url=url)
    try:
        assert client.base_url.endswith("/v1")
    finally:
        client.close()


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com/v1",
        "http://10.0.0.5:8000/v1",
        "http://localhost.evil.example/v1",
        "http://127.0.0.1.nip.io/v1",
        "ftp://api.example.com/v1",
        "api.example.com/v1",
        "https:///v1",
    ],
)
def test_rejects_non_https_remote_urls(url: str) -> None:
    with pytest.raises(GameClientError) as info:
        GameClient(base_url=url)
    assert info.value.code == "insecure_base_url"


def test_pairing_client_rejects_plain_http_remote(tmp_path: Path) -> None:
    with pytest.raises(GameClientError):
        PairingClient(base_url="http://api.example.com/v1")


def test_absolute_request_urls_are_checked_too() -> None:
    with pytest.raises(GameClientError):
        require_secure_url("http://api.example.com/v1/me")
    assert require_secure_url("https://api.example.com/v1/me")


def test_default_base_url_is_loopback() -> None:
    client = GameClient()
    try:
        assert client.base_url.startswith("http://127.0.0.1")
    finally:
        client.close()
