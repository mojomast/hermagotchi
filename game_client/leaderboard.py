"""Thin leaderboard facade over :class:`game_client.GameClient`."""

from __future__ import annotations

from typing import Any


class LeaderboardAPI:
    """Read the public top slice and the caller's near-rank window."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def top(
        self,
        *,
        season_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        near: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": int(limit),
            "offset": int(offset),
        }
        if season_id is not None:
            params["season_id"] = season_id
        if near is not None:
            params["near"] = int(near)

        request = getattr(self.client, "_request", None)
        if callable(request):
            return request("GET", "/leaderboard", params=params)

        method = getattr(self.client, "leaderboard", None)
        if callable(method):
            return method(season_id=season_id)
        raise AttributeError("client does not expose a leaderboard read")

    get = top
    read = top


def get_leaderboard(
    client: Any,
    *,
    season_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    near: int | None = None,
) -> dict[str, Any]:
    return LeaderboardAPI(client).top(
        season_id=season_id,
        limit=limit,
        offset=offset,
        near=near,
    )


__all__ = ["LeaderboardAPI", "get_leaderboard"]
