"""FastAPI router for the local Hermagotchi dashboard bridge.

The Desktop UI never receives session tokens. It talks to this local bridge,
which resolves the owner-private session from ``game_client.auth.SessionStore``
and forwards allowlisted calls to the hosted ``/v1`` service with a Bearer
header. The bridge adds the Authorization header server-side and returns only
sanitized JSON envelopes.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import sys
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from game_client import (
    DEFAULT_API_BASE_URL,
    GameClient,
    GameClientError,
    PolicyGate,
    new_idempotency_key,
)
from game_client.auth import PairingClient, SessionStore

ENV_API_BASE_URL = "HERMAGOTCHI_API_BASE_URL"

_OFFLINE_CODES = frozenset(
    {"network_disabled", "network_error", "offline", "timeout"}
)
_UNAUTHORIZED_CODES = frozenset(
    {"unauthorized", "expired", "expired_token", "invalid_grant"}
)
_PENDING_CODES = frozenset({"authorization_pending", "slow_down"})
_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "device_code",
        "authorization",
        "idempotency_key",
    }
)
_TOKEN_TEXT = re.compile(r"hg[adr]_[A-Za-z0-9_-]{8,}")

# Every proxy path is a server-relative route (without the leading "/v1").
# Unknown paths are rejected locally before any session or network work.
PROXY_ALLOWLIST = (
    r"me",
    r"wallet",
    r"ledger",
    r"catalog",
    r"pets",
    r"pets/[A-Za-z0-9_.:~-]+",
    r"pets/[A-Za-z0-9_.:~-]+/equip",
    r"pets/[A-Za-z0-9_.:~-]+/unequip",
    r"pets/[A-Za-z0-9_.:~-]+/care",
    r"goals",
    r"goals/clear",
    r"shop/purchases",
    r"challenges",
    r"challenges/[A-Za-z0-9_.:~-]+/respond",
    r"challenges/inbox",
    r"practice",
    r"matches/[A-Za-z0-9_.:~-]+",
    r"matches/[A-Za-z0-9_.:~-]+/tactics",
    r"leaderboard",
    r"bounties",
    r"bounties/[A-Za-z0-9_.:~-]+/claim",
    r"chat/channels/[A-Za-z0-9_.:~-]+/messages",
    r"chat/inbox",
    r"chat/inbox/read",
    r"chat/taunt",
    r"me/chat-settings",
    r"me/policy",
    r"friends",
    r"friends/[A-Za-z0-9_.:~-]+",
    r"friends/requests/[A-Za-z0-9_.:~-]+/respond",
    r"presence",
    r"social/history",
    r"moderation/report",
    r"blocks",
    r"blocks/[A-Za-z0-9_.:~-]+",
    r"healthz",
)
_PROXY_PATTERNS = tuple(re.compile(rf"^{pattern}$") for pattern in PROXY_ALLOWLIST)

_ASSETS_DIR = _ROOT / "assets"
_PREFERRED_MANIFEST = "manifest.launch-003.json"
_FALLBACK_MANIFEST = "manifest.json"
_ASSET_API_SUFFIX = "assets"


def _assets_dir() -> Path:
    """Return the plugin's local asset root (injectable for tests)."""

    return _ASSETS_DIR


def _manifest_path() -> Path:
    root = _assets_dir()
    preferred = root / _PREFERRED_MANIFEST
    if preferred.is_file():
        return preferred
    return root / _FALLBACK_MANIFEST


def _resolve_asset_path(relative: str) -> Path | None:
    """Resolve a request path inside the asset root, rejecting escapes."""

    text = str(relative or "").strip()
    if not text or "\x00" in text:
        return None
    normalized = text.replace("\\", "/")
    if normalized.startswith("/"):
        return None
    if any(part == ".." for part in normalized.split("/")):
        return None

    root = _assets_dir().resolve()
    try:
        candidate = (root / normalized).resolve()
    except (OSError, ValueError):
        return None
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _asset_media_type(path: Path) -> str:
    guessed, _encoding = mimetypes.guess_type(str(path))
    if isinstance(guessed, str) and guessed.startswith("image/"):
        return guessed
    return "application/octet-stream"


def _base_url() -> str:
    return os.environ.get(ENV_API_BASE_URL) or DEFAULT_API_BASE_URL


def get_session_store() -> SessionStore:
    """Return the owner-private session store for this installation."""

    return SessionStore()


def get_pairing_client() -> PairingClient:
    """Build a pairing/proxy client bound to the local session store."""

    return PairingClient(base_url=_base_url(), store=get_session_store())


def get_client() -> GameClient:
    """Build a client from non-secret runtime configuration."""

    return GameClient(base_url=_base_url())


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


def _scrub(value: Any) -> Any:
    """Remove token-like values and sensitive keys from outward payloads."""

    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                continue
            cleaned[str(key)] = _scrub(item)
        return cleaned
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, tuple):
        return [_scrub(item) for item in value]
    if isinstance(value, str):
        return _TOKEN_TEXT.sub("[redacted]", value)
    return value


def _error_body(exc: GameClientError, policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "status": _status_name(exc.code),
        "error": _scrub(exc.as_dict()),
        "policy": dict(policy),
    }


def _error_envelope(
    status: str,
    code: str,
    message: str,
    *,
    retry_after_s: int = 0,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error": {
            "code": _scrub(str(code)),
            "message": _scrub(str(message)),
            "retry_after_s": int(retry_after_s or 0),
        },
    }


def _ok_envelope(data: Any) -> dict[str, Any]:
    return {"ok": True, "status": "ok", "data": _scrub(data)}


def _ok_pair_envelope(data: Any) -> dict[str, Any]:
    """Return the standard envelope plus the raw pair fields as aliases."""

    cleaned = _scrub(data)
    body: dict[str, Any] = {"ok": True, "status": "ok", "data": cleaned}
    if isinstance(cleaned, Mapping):
        for key, value in cleaned.items():
            body.setdefault(str(key), value)
    return body


def _proxy_status(exc: GameClientError) -> str:
    if exc.code in _OFFLINE_CODES:
        return "offline"
    if exc.status_code == 401 or exc.code in _UNAUTHORIZED_CODES:
        return "unauthorized"
    if exc.status_code in {429, 500, 502, 503, 504}:
        return "unavailable"
    if exc.code in {"unavailable", "rate_limited", "slow_down"}:
        return "unavailable"
    return "http_error"


def _proxy_error(exc: GameClientError) -> dict[str, Any]:
    return _error_envelope(
        _proxy_status(exc),
        exc.code,
        exc.message,
        retry_after_s=exc.retry_after_s,
    )


def _match_proxy_path(path: str) -> str | None:
    candidate = str(path or "").strip("/")
    if not candidate or ".." in candidate.split("/"):
        return None
    for pattern in _PROXY_PATTERNS:
        if pattern.fullmatch(candidate):
            return candidate
    return None


def _read_status(client: Any) -> dict[str, Any]:
    status_method = getattr(client, "status", None)
    if callable(status_method):
        payload = status_method()
        if isinstance(payload, dict):
            return dict(payload)
    return {"health": client.health(), "me": client.me()}


class _PairingState:
    """In-memory pending device-code state for one local bridge process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, Any] | None = None

    def set(self, value: Mapping[str, Any]) -> None:
        with self._lock:
            self._pending = dict(value)

    def get(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._pending) if self._pending is not None else None

    def clear(self) -> None:
        with self._lock:
            self._pending = None


def _store_for(pair_client: Any, fallback: SessionStore | Any) -> Any:
    store = getattr(pair_client, "store", None)
    return store if store is not None else fallback


def _has_session(store: Any) -> bool:
    try:
        return bool(store.access_token)
    except Exception:
        try:
            return bool((store.load() or {}).get("access_token"))
        except Exception:
            return False


def _send_proxy_request(
    pair_client: Any,
    method: str,
    path: str,
    *,
    body: Any,
    idempotency_key: str | None,
    query: str = "",
) -> httpx.Response:
    store = getattr(pair_client, "store", None)
    session = store.load() if store is not None else {}
    session = session or {}

    def send(token: str | None) -> httpx.Response:
        headers = dict(getattr(pair_client, "_headers", {}) or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
            for key in tuple(headers):
                if key.lower() == "x-account-id":
                    headers.pop(key)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        url = pair_client._url("/" + path.lstrip("/"))
        if query:
            url = f"{url}?{query}"
        try:
            return pair_client._client.request(
                method.upper(),
                url,
                json=body if body is not None else None,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise GameClientError(
                "network_error",
                "Could not reach the Hermagotchi service.",
                payload={"transport_error": type(exc).__name__},
            ) from exc

    token = session.get("access_token")
    if not isinstance(token, str) or not token:
        token = None
    response = send(token)

    if (
        response.status_code == 401
        and isinstance(session.get("refresh_token"), str)
        and session.get("refresh_token")
    ):
        pair_client.refresh()
        new_token = store.access_token if store is not None else None
        if not new_token:
            raise GameClientError(
                "unauthorized",
                "A valid account session is required.",
                status_code=401,
            )
        response = send(new_token)

    return response


def _forward_proxy(
    pair_client: Any,
    method: str,
    path: str,
    *,
    body: Any,
    idempotency_key: str | None,
    query: str = "",
) -> Any:
    response = _send_proxy_request(
        pair_client,
        method,
        path,
        body=body,
        idempotency_key=idempotency_key,
        query=query,
    )
    return pair_client._expect(response)


async def _json_body(request: Request) -> Any:
    raw = await request.body()
    if not raw:
        return {}
    try:
        return await request.json()
    except ValueError:
        return {}


def create_router(
    *,
    base_url: str | None = None,
    policy: Mapping[str, Any] | PolicyGate | None = None,
    client_factory: Callable[[], Any] | None = None,
    client_dependency: Callable[[], Any] | None = None,
    session_store: SessionStore | None = None,
    pairing_client_factory: Callable[[], Any] | None = None,
    pairing_client: Any | None = None,
    pairing_state: _PairingState | None = None,
) -> APIRouter:
    """Create a router with injectable clients and session storage."""

    if client_dependency is None:
        if client_factory is not None:
            def client_dependency() -> Any:
                return client_factory()
        elif base_url is not None or policy is not None:
            def client_dependency() -> Any:
                return GameClient(
                    base_url=base_url or _base_url(),
                    policy=policy,
                )
        else:
            client_dependency = get_client

    configured_store = session_store

    if pairing_client is not None and pairing_client_factory is None:
        def pairing_client_factory() -> Any:
            return pairing_client

    if pairing_client_factory is None:
        if configured_store is not None:
            def pairing_client_dependency() -> Any:
                return PairingClient(
                    base_url=base_url or _base_url(),
                    store=configured_store,
                )
        else:
            pairing_client_dependency = get_pairing_client
    else:
        def pairing_client_dependency() -> Any:
            return pairing_client_factory()

    pending = pairing_state if pairing_state is not None else _PairingState()

    def store_dependency(
        pair_client: Any = Depends(pairing_client_dependency),
    ) -> Any:
        return _store_for(pair_client, configured_store or get_session_store())

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
            "health": _scrub(payload),
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
        body.update(_scrub(payload))
        body["policy"] = policy_payload
        body["asset_base_path"] = _ASSET_API_SUFFIX
        return body

    @router.get("/assets/manifest")
    def assets_manifest() -> Any:
        path = _manifest_path()
        if not path.is_file():
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "status": "not_found",
                    "error": {
                        "code": "manifest_not_found",
                        "message": "No asset manifest is available.",
                        "retry_after_s": 0,
                    },
                },
            )
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "status": "unavailable",
                    "error": {
                        "code": "manifest_unreadable",
                        "message": "The asset manifest could not be read.",
                        "retry_after_s": 0,
                    },
                },
            )
        return JSONResponse(content=manifest, media_type="application/json")

    @router.get("/assets/{path:path}")
    def assets_file(path: str) -> Any:
        candidate = _resolve_asset_path(path)
        if candidate is None:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "status": "not_found",
                    "error": {
                        "code": "asset_not_found",
                        "message": "No asset exists for that path.",
                        "retry_after_s": 0,
                    },
                },
            )
        try:
            payload = candidate.read_bytes()
        except OSError:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "status": "not_found",
                    "error": {
                        "code": "asset_not_found",
                        "message": "No asset exists for that path.",
                        "retry_after_s": 0,
                    },
                },
            )
        return Response(content=payload, media_type=_asset_media_type(candidate))

    @router.get("/assets-data/{path:path}")
    def assets_data(path: str) -> Any:
        """JSON/base64 twin of ``/assets/`` for Desktop ``ctx.rest`` (JSON-only).

        The pane turns ``data_b64`` into a Blob URL; no host token is involved.
        """
        candidate = _resolve_asset_path(path)
        payload: bytes | None = None
        if candidate is not None:
            try:
                payload = candidate.read_bytes()
            except OSError:
                payload = None
        if payload is None:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "status": "not_found",
                    "error": {
                        "code": "asset_not_found",
                        "message": "No asset exists for that path.",
                        "retry_after_s": 0,
                    },
                },
            )
        return {
            "ok": True,
            "status": "ok",
            "mime": _asset_media_type(candidate),
            "data_b64": base64.b64encode(payload).decode("ascii"),
        }

    @router.post("/pair/start")
    async def pair_start(
        request: Request,
        pair_client: Any = Depends(pairing_client_dependency),
    ) -> dict[str, Any]:
        payload = await _json_body(request)
        if not isinstance(payload, Mapping):
            return _error_envelope(
                "http_error", "invalid_arguments", "A JSON object is required."
            )
        device_name = payload.get("device_name")
        new_account = bool(payload.get("new_account"))
        public_handle = payload.get("public_handle")
        if public_handle is not None and not isinstance(public_handle, str):
            return _error_envelope(
                "http_error", "invalid_arguments", "public_handle must be a string."
            )
        try:
            started = pair_client.start(
                device_name,
                new_account=new_account,
                public_handle=public_handle,
            )
        except GameClientError as exc:
            return _proxy_error(exc)

        device_code = started.get("device_code") if isinstance(started, Mapping) else None
        if not device_code:
            return _error_envelope(
                "unavailable",
                "invalid_response",
                "The pairing service did not return a device challenge.",
            )
        pending.set(
            {
                "device_code": device_code,
                "user_code": started.get("user_code"),
                "expires_at": started.get("expires_at"),
                "interval_s": started.get("interval_s"),
            }
        )
        data = {
            "user_code": started.get("user_code"),
            "expires_at": started.get("expires_at"),
            "paired": False,
        }
        if started.get("interval_s") is not None:
            data["interval_s"] = started.get("interval_s")
        return _ok_pair_envelope(data)

    @router.post("/pair/poll")
    def pair_poll(
        pair_client: Any = Depends(pairing_client_dependency),
        store: SessionStore = Depends(store_dependency),
    ) -> dict[str, Any]:
        current = pending.get()
        if current is None:
            if _has_session(store):
                return _ok_pair_envelope(
                    {"paired": True, "account_id": store.account_id}
                )
            return _ok_pair_envelope(
                {"paired": False, "account_id": None, "status": "idle"}
            )

        try:
            tokens = pair_client.poll_token(current.get("device_code"))
        except GameClientError as exc:
            if exc.code in _PENDING_CODES:
                return _ok_pair_envelope(
                    {
                        "paired": False,
                        "account_id": None,
                        "status": "pending",
                        "retry_after_s": exc.retry_after_s,
                    }
                )
            if exc.code == "expired_token":
                pending.clear()
                return _error_envelope(
                    "expired",
                    exc.code,
                    exc.message,
                    retry_after_s=exc.retry_after_s,
                )
            if exc.code == "invalid_grant":
                pending.clear()
            return _proxy_error(exc)

        pending.clear()
        account_id = (
            tokens.get("account_id") if isinstance(tokens, Mapping) else None
        ) or store.account_id
        return _ok_pair_envelope({"paired": True, "account_id": account_id})

    @router.post("/pair/approve")
    async def pair_approve(
        request: Request,
        pair_client: Any = Depends(pairing_client_dependency),
        store: SessionStore = Depends(store_dependency),
    ) -> dict[str, Any]:
        if not _has_session(store):
            return _error_envelope(
                "auth_missing",
                "auth_missing",
                "This device is not paired yet.",
            )
        payload = await _json_body(request)
        user_code = payload.get("user_code") if isinstance(payload, Mapping) else None
        try:
            result = pair_client.approve(user_code)
        except GameClientError as exc:
            return _proxy_error(exc)
        return _ok_pair_envelope(result)

    @router.get("/pair/devices")
    def pair_devices(
        pair_client: Any = Depends(pairing_client_dependency),
        store: SessionStore = Depends(store_dependency),
    ) -> dict[str, Any]:
        if not _has_session(store):
            return _error_envelope(
                "auth_missing",
                "auth_missing",
                "This device is not paired yet.",
            )
        try:
            result = pair_client.list_devices()
        except GameClientError as exc:
            return _proxy_error(exc)
        return _ok_pair_envelope(result)

    @router.post("/pair/devices/{device_id}/revoke")
    def pair_revoke(
        device_id: str,
        pair_client: Any = Depends(pairing_client_dependency),
        store: SessionStore = Depends(store_dependency),
    ) -> dict[str, Any]:
        if not _has_session(store):
            return _error_envelope(
                "auth_missing",
                "auth_missing",
                "This device is not paired yet.",
            )
        try:
            result = pair_client.revoke(device_id)
        except GameClientError as exc:
            return _proxy_error(exc)
        return _ok_pair_envelope(result)

    @router.post("/pair/logout")
    def pair_logout(
        pair_client: Any = Depends(pairing_client_dependency),
        store: SessionStore = Depends(store_dependency),
    ) -> dict[str, Any]:
        pending.clear()
        if not _has_session(store):
            return _ok_pair_envelope({"logged_out": True, "paired": False})
        try:
            result = pair_client.logout()
        except GameClientError as exc:
            return _proxy_error(exc)
        return _ok_pair_envelope(result)

    @router.api_route(
        "/proxy/v1/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    )
    async def proxy(
        path: str,
        request: Request,
        pair_client: Any = Depends(pairing_client_dependency),
        store: SessionStore = Depends(store_dependency),
    ) -> Any:
        matched = _match_proxy_path(path)
        if matched is None:
            return JSONResponse(
                status_code=404,
                content=_error_envelope(
                    "not_allowed",
                    "not_allowed",
                    "That bridge path is not allowlisted.",
                ),
            )
        if not _has_session(store):
            return _error_envelope(
                "auth_missing",
                "auth_missing",
                "This device is not paired yet.",
            )

        method = request.method.upper()
        body = await _json_body(request) if method != "GET" else None
        # Desktop ctx.rest cannot set custom headers, so the key may also ride
        # as ``?idempotency_key=``; it is stripped before forwarding upstream.
        header_key = request.headers.get("Idempotency-Key")
        query_key = request.query_params.get("idempotency_key")
        raw_key = header_key or query_key
        idempotency_key = raw_key.strip() if raw_key else None
        forward_query = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}"
            for k, v in request.query_params.multi_items()
            if k != "idempotency_key"
        )
        if method != "GET" and not idempotency_key:
            idempotency_key = new_idempotency_key()
        try:
            payload = _forward_proxy(
                pair_client,
                method,
                matched,
                body=body,
                idempotency_key=idempotency_key,
                query=forward_query,
            )
        except GameClientError as exc:
            return _proxy_error(exc)
        return _ok_envelope(payload)

    return router


router = create_router()
