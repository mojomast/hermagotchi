"""FastAPI router for the local Hermagotchi dashboard bridge."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from game_client import (
    DEFAULT_API_BASE_URL,
    GameClient,
    GameClientError,
    PolicyGate,
)

ENV_API_BASE_URL = "HERMAGOTCHI_API_BASE_URL"

_OFFLINE_CODES = frozenset(
    {"network_disabled", "network_error", "offline", "timeout"}
)


def get_client() -> GameClient:
    """Build a client from non-secret runtime configuration."""

    base_url = os.environ.get(ENV_API_BASE_URL) or DEFAULT_API_BASE_URL
    return GameClient(base_url=base_url)


def _policy_dict(client: Any) -> dict[str, Any]:
    policy = getattr(client, "policy", None)
    if policy is None:
        return {}
    if isinstance(policy, PolicyGate):
        return policy.as_dict()
    as_dict = getattr(policy, "as_dict", None)
    if callable(as_dict):
        return dict(as_dict())
    if isinstance(policy, Mapping):
        return dict(policy)
    return {}


def _status_name(code: str) -> str:
    if code in _OFFLINE_CODES:
        return "offline"
    if code in {"unauthorized", "expired", "disabled"}:
        return code
    return "unavailable"


def _error_body(exc: GameClientError, policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "status": _status_name(exc.code),
        "error": exc.as_dict(),
        "policy": dict(policy),
    }


def _read_status(client: Any) -> dict[str, Any]:
    status_method = getattr(client, "status", None)
    if callable(status_method):
        payload = status_method()
        if isinstance(payload, dict):
            return dict(payload)
    return {"health": client.health(), "me": client.me()}


def create_router(
    *,
    base_url: str | None = None,
    policy: Mapping[str, Any] | PolicyGate | None = None,
    client_factory: Callable[[], Any] | None = None,
    client_dependency: Callable[[], Any] | None = None,
) -> APIRouter:
    """Create a router with an injectable base URL or client factory."""

    if client_dependency is None:
        if client_factory is not None:
            def client_dependency() -> Any:
                return client_factory()
        elif base_url is not None or policy is not None:
            def client_dependency() -> Any:
                return GameClient(
                    base_url=base_url or DEFAULT_API_BASE_URL,
                    policy=policy,
                )
        else:
            client_dependency = get_client

    router = APIRouter()

    @router.get("/health")
    def health(client: Any = Depends(client_dependency)) -> dict[str, Any]:
        policy_payload = _policy_dict(client)
        try:
            payload = client.health()
        except GameClientError as exc:
            return _error_body(exc, policy_payload)
        return {
            "ok": True,
            "status": "ok",
            "health": payload,
            "policy": policy_payload,
        }

    @router.get("/status")
    def status(client: Any = Depends(client_dependency)) -> dict[str, Any]:
        policy_payload = _policy_dict(client)
        try:
            payload = _read_status(client)
        except GameClientError as exc:
            return _error_body(exc, policy_payload)
        body: dict[str, Any] = {"ok": True, "status": "ok"}
        body.update(payload)
        body["policy"] = policy_payload
        return body

    return router


router = create_router()
