"""Thin bounties facade over :class:`game_client.GameClient`."""

from __future__ import annotations

from typing import Any


class BountiesAPI:
    """Expose bounty reads/claims without duplicating transport logic."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def list(self) -> dict[str, Any]:
        method = getattr(self.client, "list_bounties", None)
        if callable(method):
            return method()
        return self.client._request("GET", "/bounties")

    def claim(
        self, bounty_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        method = getattr(self.client, "claim_bounty", None)
        if callable(method):
            return method(bounty_id, idempotency_key=idempotency_key)
        return self.client._request(
            "POST",
            f"/bounties/{bounty_id}/claim",
            json_body={},
            action="meta.claim_bounty",
            idempotency_key=idempotency_key,
        )


def list_bounties(client: Any) -> dict[str, Any]:
    return BountiesAPI(client).list()


def claim_bounty(
    client: Any, bounty_id: str, *, idempotency_key: str | None = None
) -> dict[str, Any]:
    return BountiesAPI(client).claim(bounty_id, idempotency_key=idempotency_key)


__all__ = ["BountiesAPI", "claim_bounty", "list_bounties"]
