"""Thin chat, block and moderation facade over :class:`game_client.GameClient`.

Chat text returned by these calls is untrusted display data. Callers must not
feed it into prompts, tools or executable contexts.
"""

from __future__ import annotations

from typing import Any


class SocialAPI:
    def __init__(self, client: Any) -> None:
        self.client = client

    def read(
        self,
        channel_id: str,
        *,
        limit: int = 50,
        before: str | None = None,
    ) -> dict[str, Any]:
        method = getattr(self.client, "read_messages", None)
        if callable(method):
            return method(channel_id, limit=limit, before=before)
        params: dict[str, Any] = {"limit": int(limit)}
        if before is not None:
            params["before"] = before
        return self.client._request(
            "GET", f"/chat/channels/{channel_id}/messages", params=params
        )

    def send(
        self,
        channel_id: str | None = None,
        body: str | None = None,
        *,
        target: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        method = getattr(self.client, "send_message", None)
        if callable(method):
            if target is not None:
                return method(
                    body=body, target=target, idempotency_key=idempotency_key
                )
            return method(channel_id, body, idempotency_key=idempotency_key)
        if target is not None:
            return self.client._request(
                "POST",
                "/chat/dm",
                json_body={"target": target, "body": body},
                action="social.send",
                idempotency_key=idempotency_key,
            )
        return self.client._request(
            "POST",
            f"/chat/channels/{channel_id}/messages",
            json_body={"body": body},
            action="social.send",
            idempotency_key=idempotency_key,
        )

    def inbox(self) -> dict[str, Any]:
        method = getattr(self.client, "inbox", None)
        if callable(method):
            return method()
        return self.client._request("GET", "/chat/inbox")

    def friends(
        self,
        action: str = "list",
        *,
        target_id: str | None = None,
        target: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        method = getattr(self.client, "friends", None)
        if callable(method):
            kwargs: dict[str, Any] = {"idempotency_key": idempotency_key}
            if target_id is not None:
                kwargs["target_id"] = target_id
            if target is not None:
                kwargs["target"] = target
            return method(action, **kwargs)
        choice = str(action or "list").strip().lower()
        if choice == "list":
            return self.client._request("GET", "/friends")
        value = target_id if isinstance(target_id, str) and target_id.strip() else target
        if not isinstance(value, str) or not value.strip():
            raise ValueError("target_id is required for friend mutations")
        value = value.strip()
        if choice == "add":
            return self.client._request(
                "POST",
                "/friends",
                json_body={"target_id": value},
                action="social.friends.add",
                idempotency_key=idempotency_key,
            )
        if choice in {"accept", "decline"}:
            return self.client._request(
                "POST",
                f"/friends/{value}/{choice}",
                json_body={},
                action=f"social.friends.{choice}",
                idempotency_key=idempotency_key,
            )
        if choice == "remove":
            return self.client._request(
                "DELETE",
                f"/friends/{value}",
                action="social.friends.remove",
                idempotency_key=idempotency_key,
            )
        raise ValueError(f"unknown friend action: {action}")

    def list_friends(self) -> dict[str, Any]:
        return self.friends("list")

    def add_friend(
        self, target_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        return self.friends(
            "add", target_id=target_id, idempotency_key=idempotency_key
        )

    def accept_friend(
        self, target_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        return self.friends(
            "accept", target_id=target_id, idempotency_key=idempotency_key
        )

    def decline_friend(
        self, target_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        return self.friends(
            "decline", target_id=target_id, idempotency_key=idempotency_key
        )

    def remove_friend(
        self, target_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        return self.friends(
            "remove", target_id=target_id, idempotency_key=idempotency_key
        )

    def history(self, *, filter: str = "all") -> dict[str, Any]:
        method = getattr(self.client, "social_history", None)
        if callable(method):
            return method(filter=filter)
        choice = str(filter or "all").strip().lower()
        return self.client._request(
            "GET", "/social/history", params={"filter": choice}
        )

    def taunt(
        self,
        match_id: str,
        body: str,
        phase: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        method = getattr(self.client, "taunt", None)
        if callable(method):
            return method(
                match_id,
                body,
                phase,
                idempotency_key=idempotency_key,
            )
        return self.client._request(
            "POST",
            "/chat/taunt",
            json_body={"match_id": match_id, "body": body, "phase": phase},
            action="social.taunt",
            idempotency_key=idempotency_key,
        )

    def report(
        self,
        target_type: str,
        target_id: str,
        reason: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        method = getattr(self.client, "report", None)
        if callable(method):
            return method(
                target_type,
                target_id,
                reason,
                idempotency_key=idempotency_key,
            )
        return self.client._request(
            "POST",
            "/moderation/report",
            json_body={
                "target_type": target_type,
                "target_id": target_id,
                "reason": reason,
            },
            action="moderation.report",
            idempotency_key=idempotency_key,
        )

    def block(
        self, blocked_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        return self.client._request(
            "POST",
            "/blocks",
            json_body={"blocked_id": blocked_id},
            action="social.block",
            idempotency_key=idempotency_key,
        )

    def unblock(
        self, blocked_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        return self.client._request(
            "DELETE",
            f"/blocks/{blocked_id}",
            action="social.unblock",
            idempotency_key=idempotency_key,
        )

    def blocks(self) -> dict[str, Any]:
        return self.client._request("GET", "/blocks")


def read_messages(
    client: Any,
    channel_id: str,
    *,
    limit: int = 50,
    before: str | None = None,
) -> dict[str, Any]:
    return SocialAPI(client).read(channel_id, limit=limit, before=before)


def send_message(
    client: Any,
    channel_id: str | None = None,
    body: str | None = None,
    *,
    target: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    return SocialAPI(client).send(
        channel_id,
        body,
        target=target,
        idempotency_key=idempotency_key,
    )


def inbox(client: Any) -> dict[str, Any]:
    return SocialAPI(client).inbox()


def friends(
    client: Any,
    action: str = "list",
    *,
    target_id: str | None = None,
    target: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    return SocialAPI(client).friends(
        action,
        target_id=target_id,
        target=target,
        idempotency_key=idempotency_key,
    )


def list_friends(client: Any) -> dict[str, Any]:
    return SocialAPI(client).list_friends()


def add_friend(
    client: Any, target_id: str, *, idempotency_key: str | None = None
) -> dict[str, Any]:
    return SocialAPI(client).add_friend(
        target_id, idempotency_key=idempotency_key
    )


def accept_friend(
    client: Any, target_id: str, *, idempotency_key: str | None = None
) -> dict[str, Any]:
    return SocialAPI(client).accept_friend(
        target_id, idempotency_key=idempotency_key
    )


def decline_friend(
    client: Any, target_id: str, *, idempotency_key: str | None = None
) -> dict[str, Any]:
    return SocialAPI(client).decline_friend(
        target_id, idempotency_key=idempotency_key
    )


def remove_friend(
    client: Any, target_id: str, *, idempotency_key: str | None = None
) -> dict[str, Any]:
    return SocialAPI(client).remove_friend(
        target_id, idempotency_key=idempotency_key
    )


def social_history(client: Any, *, filter: str = "all") -> dict[str, Any]:
    return SocialAPI(client).history(filter=filter)


def taunt(
    client: Any,
    match_id: str,
    body: str,
    phase: str,
    *,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    return SocialAPI(client).taunt(
        match_id,
        body,
        phase,
        idempotency_key=idempotency_key,
    )


def report_abuse(
    client: Any,
    target_type: str,
    target_id: str,
    reason: str,
    *,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    return SocialAPI(client).report(
        target_type,
        target_id,
        reason,
        idempotency_key=idempotency_key,
    )


def block_account(
    client: Any, blocked_id: str, *, idempotency_key: str | None = None
) -> dict[str, Any]:
    return SocialAPI(client).block(blocked_id, idempotency_key=idempotency_key)


def unblock_account(
    client: Any, blocked_id: str, *, idempotency_key: str | None = None
) -> dict[str, Any]:
    return SocialAPI(client).unblock(blocked_id, idempotency_key=idempotency_key)


__all__ = [
    "SocialAPI",
    "accept_friend",
    "add_friend",
    "block_account",
    "decline_friend",
    "friends",
    "inbox",
    "list_friends",
    "read_messages",
    "remove_friend",
    "report_abuse",
    "send_message",
    "social_history",
    "taunt",
    "unblock_account",
]
