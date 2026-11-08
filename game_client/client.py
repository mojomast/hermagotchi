"""Typed HTTP client for the hosted Hermagotchi ``/v1`` API."""

from __future__ import annotations

import ipaddress
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx

from .errors import GameClientError
from .idempotency import idempotency_key as new_idempotency_key
from .policy import PolicyGate

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/v1"
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    host = host.strip("[]").lower()
    if host in _LOOPBACK_HOSTS or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def require_secure_url(url: str) -> str:
    """Reject game API URLs that are not HTTPS, except plain-HTTP loopback.

    The README promises HTTPS to the hosted game; plaintext HTTP is only
    accepted for a local dev server on loopback (127.0.0.0/8, ::1, localhost).
    """

    parts = urlsplit(url)
    scheme = (parts.scheme or "").lower()
    if scheme == "https" and parts.hostname:
        return url
    if scheme == "http" and _is_loopback_host(parts.hostname):
        return url
    raise GameClientError(
        "insecure_base_url",
        "Game API URL must use https:// (plain http:// is only allowed for loopback).",
    )


def _normalize_base_url(base_url: str | None) -> str:
    value = (base_url or DEFAULT_API_BASE_URL).strip().rstrip("/")
    require_secure_url(value)
    if not value.endswith("/v1"):
        value = f"{value}/v1"
    return value


class GameClient:
    """Thin, typed wrapper around the contracts-v1 game API.

    Read helpers are safe to call. Every mutation passes through ``PolicyGate``
    before a request is made, and only safe GET requests are retried.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_API_BASE_URL,
        *,
        policy: Mapping[str, Any] | PolicyGate | None = None,
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
        headers: Mapping[str, str] | None = None,
        auth_token: str | None = None,
        token_provider: Callable[[], str | None] | None = None,
        max_retries: int = 2,
        backoff_s: float = 0.25,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.policy = policy if isinstance(policy, PolicyGate) else PolicyGate(policy)
        self.max_retries = max(0, int(max_retries))
        self.backoff_s = max(0.0, float(backoff_s))
        self._sleep = sleep or time.sleep
        self._owns_client = http_client is None
        if http_client is None and transport is not None:
            http_client = httpx.Client(transport=transport, timeout=timeout)
        self._client = http_client or httpx.Client(timeout=timeout)
        merged_headers = dict(headers or {})
        if auth_token:
            merged_headers.setdefault("Authorization", f"Bearer {auth_token}")
        self._headers = merged_headers
        self._token_provider = token_provider

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "GameClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return require_secure_url(path)
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request_headers(self) -> dict[str, str]:
        headers = dict(self._headers)
        provider = self._token_provider
        if provider is None:
            return headers
        if callable(provider):
            token = provider()
        elif isinstance(provider, str):
            token = provider
        else:
            token = getattr(provider, "access_token", None)
        if not token:
            return headers
        headers["Authorization"] = f"Bearer {token}"
        for key in tuple(headers):
            if key.lower() == "x-account-id":
                headers.pop(key)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        action: str | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        method = method.upper()
        headers = self._request_headers()
        body: dict[str, Any] | None = dict(json_body) if json_body is not None else None

        if method != "GET":
            self.policy.check_mutation(action or method.lower())
            key = idempotency_key or new_idempotency_key()
            headers["Idempotency-Key"] = key
            if body is None:
                body = {}
            body.setdefault("idempotency_key", key)

        attempts = 1 + (self.max_retries if method == "GET" else 0)
        url = self._url(path)
        for attempt in range(attempts):
            try:
                response = self._client.request(
                    method,
                    url,
                    params=params,
                    json=body,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                if method == "GET" and attempt < attempts - 1:
                    self._sleep(self._backoff(attempt))
                    continue
                raise GameClientError(
                    "network_error",
                    "Could not reach the Hermagotchi service.",
                    payload={"transport_error": type(exc).__name__},
                ) from exc

            if response.is_success:
                return self._decode(response)

            if (
                method == "GET"
                and response.status_code in RETRYABLE_STATUS_CODES
                and attempt < attempts - 1
            ):
                self._sleep(self._retry_after(response, attempt))
                continue

            raise self._error_from_response(response)

        raise GameClientError(
            "network_error",
            "Could not reach the Hermagotchi service.",
        )

    def _backoff(self, attempt: int) -> float:
        return self.backoff_s * (2**attempt)

    def _retry_after(self, response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("Retry-After")
        if header:
            try:
                value = float(header)
            except ValueError:
                value = -1.0
            if value >= 0:
                return value
        return self._backoff(attempt)

    def _decode(self, response: httpx.Response) -> Any:
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise GameClientError(
                "invalid_response",
                "The Hermagotchi service returned invalid JSON.",
                status_code=response.status_code,
            ) from exc

    def _error_from_response(self, response: httpx.Response) -> GameClientError:
        payload: dict[str, Any] = {}
        if response.content:
            try:
                decoded = response.json()
            except ValueError:
                decoded = None
            if isinstance(decoded, dict):
                payload = decoded

        code = str(payload.get("code") or f"http_{response.status_code}")
        message = str(
            payload.get("message") or response.reason_phrase or "Request failed."
        )
        try:
            retry_after_s = int(payload.get("retry_after_s") or 0)
        except (TypeError, ValueError):
            retry_after_s = 0
        correlation_id = payload.get("correlation_id")
        return GameClientError(
            code,
            message,
            status_code=response.status_code,
            retry_after_s=retry_after_s,
            correlation_id=correlation_id,
            payload=payload,
        )

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/healthz")

    def me(self) -> dict[str, Any]:
        return self._request("GET", "/me")

    def status(self) -> dict[str, Any]:
        return {
            "health": self.health(),
            "me": self.me(),
            "policy": self.policy.as_dict(),
        }

    def adopt_pet(
        self,
        species: str,
        *,
        name: str | None = None,
        mode: str = "human",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"species": species, "mode": mode}
        if name is not None:
            body["name"] = name
        return self._request(
            "POST",
            "/pets",
            json_body=body,
            action="pet.adopt",
            idempotency_key=idempotency_key,
        )

    def get_pet(self, pet_id: str) -> dict[str, Any]:
        return self._request("GET", f"/pets/{pet_id}")

    def care_pet(
        self,
        pet_id: str,
        action: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/pets/{pet_id}/care",
            json_body={"action": action},
            action="pet.care",
            idempotency_key=idempotency_key,
        )

    def equip(
        self,
        pet_id: str,
        item_id: str,
        slot: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/pets/{pet_id}/equip",
            json_body={"item_id": item_id, "slot": slot},
            action="shop.equip",
            idempotency_key=idempotency_key,
        )

    def catalog(self) -> dict[str, Any]:
        return self._request("GET", "/catalog")

    def wallet(self) -> dict[str, Any]:
        return self._request("GET", "/wallet")

    def ledger(
        self, *, limit: int = 20, offset: int = 0
    ) -> dict[str, Any]:
        return self._request(
            "GET", "/ledger", params={"limit": int(limit), "offset": int(offset)}
        )

    def purchase(
        self,
        item_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/shop/purchases",
            json_body={"item_id": item_id},
            action="shop.buy",
            idempotency_key=idempotency_key,
        )

    def create_challenge(
        self,
        opponent_id: str | None = None,
        *,
        defender_id: str | None = None,
        mode: str = "casual",
        expires_in_s: int | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"mode": mode}
        if defender_id is not None:
            body["defender_id"] = defender_id
        if opponent_id is not None:
            body["opponent_id"] = opponent_id
        if expires_in_s is not None:
            body["expires_in_s"] = int(expires_in_s)
        return self._request(
            "POST",
            "/challenges",
            json_body=body,
            action="challenge.invite",
            idempotency_key=idempotency_key,
        )

    def respond_challenge(
        self,
        challenge_id: str,
        action: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/challenges/{challenge_id}/respond",
            json_body={"action": action},
            action="challenge.respond",
            idempotency_key=idempotency_key,
        )

    def submit_tactics(
        self,
        match_id: str,
        card: Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/matches/{match_id}/tactics",
            json_body={"card": dict(card)},
            action="challenge.submit_tactics",
            idempotency_key=idempotency_key,
        )

    def get_match(self, match_id: str) -> dict[str, Any]:
        return self._request("GET", f"/matches/{match_id}")

    def list_bounties(self) -> dict[str, Any]:
        return self._request("GET", "/bounties")

    def claim_bounty(
        self,
        bounty_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/bounties/{bounty_id}/claim",
            json_body={},
            action="meta.claim_bounty",
            idempotency_key=idempotency_key,
        )

    def leaderboard(self, *, season_id: str | None = None) -> dict[str, Any]:
        params = {"season_id": season_id} if season_id is not None else None
        return self._request("GET", "/leaderboard", params=params)

    def read_messages(
        self,
        channel_id: str,
        *,
        limit: int = 50,
        before: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": int(limit)}
        if before is not None:
            params["before"] = before
        return self._request(
            "GET", f"/chat/channels/{channel_id}/messages", params=params
        )

    def send_message(
        self,
        channel_id: str | None = None,
        body: str | None = None,
        *,
        target: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if target is not None:
            return self._request(
                "POST",
                "/chat/dm",
                json_body={"target": target, "body": body},
                action="social.send",
                idempotency_key=idempotency_key,
            )
        return self._request(
            "POST",
            f"/chat/channels/{channel_id}/messages",
            json_body={"body": body},
            action="social.send",
            idempotency_key=idempotency_key,
        )

    def inbox(self) -> dict[str, Any]:
        return self._request("GET", "/chat/inbox")

    def friends(
        self,
        action: str = "list",
        *,
        target_id: str | None = None,
        target: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        choice = str(action or "list").strip().lower()
        if choice == "list":
            return self._request("GET", "/friends")
        value = target_id if isinstance(target_id, str) and target_id.strip() else target
        if not isinstance(value, str) or not value.strip():
            raise ValueError("target_id is required for friend mutations")
        value = value.strip()
        if choice == "add":
            return self._request(
                "POST",
                "/friends",
                json_body={"target_id": value},
                action="social.friends.add",
                idempotency_key=idempotency_key,
            )
        if choice in {"accept", "decline"}:
            return self._request(
                "POST",
                f"/friends/{value}/{choice}",
                json_body={},
                action=f"social.friends.{choice}",
                idempotency_key=idempotency_key,
            )
        if choice == "remove":
            return self._request(
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

    def social_history(self, *, filter: str = "all") -> dict[str, Any]:
        choice = str(filter or "all").strip().lower()
        return self._request(
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
        return self._request(
            "POST",
            "/chat/taunt",
            json_body={
                "match_id": match_id,
                "body": body,
                "phase": phase,
            },
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
        return self._request(
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

    get_health = health
    get_me = me
    create_pet = adopt_pet
    pets_adopt = adopt_pet
    pet_care = care_pet
    get_wallet = wallet
    get_ledger = ledger
    get_catalog = catalog
    shop_catalog = catalog
    buy = purchase
    shop_buy = purchase
    shop_purchase = purchase
    shop_equip = equip
    invite = create_challenge
    challenge_invite = create_challenge
    challenge_respond = respond_challenge
    bounties = list_bounties
    get_match_state = get_match
    chat_inbox = inbox
    chat_taunt = taunt
    send_dm = send_message
    history = social_history
