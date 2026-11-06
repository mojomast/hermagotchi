"""Hermagotchi hosted API client, policy gate, and idempotency helpers."""

from __future__ import annotations

from .client import DEFAULT_API_BASE_URL, GameClient
from .errors import GameClientError, PolicyDeniedError
from .idempotency import idempotency_key, make_idempotency_key, new_idempotency_key
from .policy import DEFAULT_POLICY, PolicyGate

__all__ = [
    "DEFAULT_API_BASE_URL",
    "DEFAULT_POLICY",
    "GameClient",
    "GameClientError",
    "PolicyDeniedError",
    "PolicyGate",
    "idempotency_key",
    "make_idempotency_key",
    "new_idempotency_key",
]
