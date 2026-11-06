"""Idempotency-key helpers shared by client mutations."""

from __future__ import annotations

import uuid


def idempotency_key() -> str:
    """Return a fresh client-generated UUID suitable for one mutation."""

    return str(uuid.uuid4())


def new_idempotency_key() -> str:
    """Compatibility alias for callers that prefer an explicit name."""

    return idempotency_key()


def make_idempotency_key() -> str:
    """Compatibility alias used by some plugin wiring examples."""

    return idempotency_key()
