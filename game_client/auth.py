"""Device pairing and local session storage for the Hermagotchi client.

The server is the only authority for tokens. This module keeps the short-lived
session material on disk with owner-only permissions, negotiates pairing through
the ``/v1/auth`` endpoints, and never includes token values in representations or
error payloads.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from .client import DEFAULT_API_BASE_URL, _normalize_base_url, require_secure_url
from .errors import GameClientError

USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ23456789"
DEFAULT_PAIRING_TTL_S = 600
DEFAULT_ACCESS_TTL_S = 3600
DEFAULT_REFRESH_TTL_S = 30 * 24 * 60 * 60
DEFAULT_INTERVAL_S = 5

_SESSION_FIELDS = (
    "access_token",
    "refresh_token",
    "token_type",
    "expires_in",
    "refresh_expires_in",
    "account_id",
    "device_id",
    "expires_at",
    "refresh_expires_at",
    "obtained_at",
)
_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "device_code",
        "authorization",
        "idempotency_key",
    }
)
_TOKEN_RE = re.compile(r"hg[adr]_[A-Za-z0-9_-]{8,}")
_USER_CODE_SEPARATORS = re.compile(r"[\s-]+")


def data_dir(environ: Mapping[str, str] | None = None) -> Path:
    """Return the Hermes plugin data root for this installation."""

    env = os.environ if environ is None else environ
    configured = str(env.get("HERMES_PLUGIN_DATA_DIR") or "").strip()
    if configured:
        return Path(configured).expanduser()
    home = str(env.get("HERMES_HOME") or "").strip()
    if home:
        return Path(home).expanduser() / "plugins_data"
    return Path.home() / ".hermes" / "plugins_data"


def default_session_path(environ: Mapping[str, str] | None = None) -> Path:
    return data_dir(environ) / "hermagotchi" / "session.json"


def normalise_user_code(value: Any) -> str:
    """Upper-case a user code and strip spaces and dashes."""

    return _USER_CODE_SEPARATORS.sub("", str(value or "")).upper()


def format_user_code(value: Any) -> str:
    normalised = normalise_user_code(value)
    if len(normalised) == 8:
        return f"{normalised[:4]}-{normalised[4:]}"
    return normalised


def is_valid_user_code(value: Any) -> bool:
    normalised = normalise_user_code(value)
    return len(normalised) == 8 and all(
        char in USER_CODE_ALPHABET for char in normalised
    )


def _session_record(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: values[field]
        for field in _SESSION_FIELDS
        if field in values and values[field] is not None
    }


def _redact_text(value: str) -> str:
    return _TOKEN_RE.sub("[redacted]", value)


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: (
                "[redacted]"
                if str(key).lower() in _SENSITIVE_KEYS
                else _sanitize(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


class SessionStore:
    """Owner-private JSON store for one Hermagotchi device session."""

    def __init__(
        self,
        path: str | os.PathLike[str] | None = None,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else default_session_path(environ)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(path={str(self.path)!r}, "
            f"paired={self.has_session})"
        )

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    @property
    def has_session(self) -> bool:
        return self.access_token is not None

    @property
    def paired(self) -> bool:
        return self.has_session

    def _peek(self) -> dict[str, Any]:
        data = self.load()
        return data or {}

    @property
    def access_token(self) -> str | None:
        value = self._peek().get("access_token")
        return value if isinstance(value, str) and value else None

    @property
    def refresh_token(self) -> str | None:
        value = self._peek().get("refresh_token")
        return value if isinstance(value, str) and value else None

    @property
    def account_id(self) -> str | None:
        value = self._peek().get("account_id")
        return value if isinstance(value, str) and value else None

    @property
    def device_id(self) -> str | None:
        value = self._peek().get("device_id")
        return value if isinstance(value, str) and value else None

    @property
    def current_device_id(self) -> str | None:
        return self.device_id

    def _ensure_parent(self) -> None:
        parent = self.path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "nt" and parent not in {Path("."), Path("/")}:
            try:
                os.chmod(parent, 0o700)
            except OSError:
                pass

    def load(self) -> dict[str, Any] | None:
        try:
            text = self.path.read_text(encoding="utf-8")
        except (FileNotFoundError, NotADirectoryError):
            return None
        except OSError:
            return None
        try:
            value = json.loads(text)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    read = load

    def save(self, values: Mapping[str, Any]) -> dict[str, Any]:
        record = _session_record(values)
        self._ensure_parent()
        temp = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(temp, flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle, ensure_ascii=False, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            if os.name != "nt":
                os.chmod(temp, 0o600)
            os.replace(temp, self.path)
            if os.name != "nt":
                os.chmod(self.path, 0o600)
        except BaseException:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise
        return record

    write = save

    save_tokens = save

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return
        except OSError:
            return

    delete = clear

    def as_dict(self) -> dict[str, Any]:
        return dict(self._peek())


class PairingClient:
    """Small httpx client for the ``/v1/auth`` device-pairing contract."""

    def __init__(
        self,
        base_url: str = DEFAULT_API_BASE_URL,
        *,
        store: SessionStore | None = None,
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
        headers: Mapping[str, str] | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.store = store or SessionStore(environ=environ)
        self._headers = dict(headers or {})
        self._owns_client = http_client is None
        if http_client is None and transport is not None:
            http_client = httpx.Client(transport=transport, timeout=timeout)
        self._client = http_client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "PairingClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return require_secure_url(path)
        return f"{self.base_url}/{path.lstrip('/')}"

    def _send(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        token: str | None = None,
    ) -> httpx.Response:
        headers = dict(self._headers)
        if token:
            headers["Authorization"] = f"Bearer {token}"
            for key in tuple(headers):
                if key.lower() == "x-account-id":
                    headers.pop(key)
        try:
            return self._client.request(
                method.upper(),
                self._url(path),
                json=dict(body) if body is not None else None,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise GameClientError(
                "network_error",
                "Could not reach the Hermagotchi service.",
                payload={"transport_error": type(exc).__name__},
            ) from exc

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
                payload = _sanitize(decoded)

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
            _redact_text(code),
            _redact_text(message),
            status_code=response.status_code,
            retry_after_s=retry_after_s,
            correlation_id=correlation_id,
            payload=payload,
        )

    def _expect(self, response: httpx.Response) -> Any:
        if response.is_success:
            return self._decode(response)
        raise self._error_from_response(response)

    def _authorized(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        allow_refresh: bool = True,
    ) -> Any:
        session = self.store.load() or {}
        token = session.get("access_token")
        if not isinstance(token, str) or not token:
            token = None
        response = self._send(method, path, body=body, token=token)

        if (
            response.status_code == 401
            and allow_refresh
            and isinstance(session.get("refresh_token"), str)
            and session.get("refresh_token")
        ):
            self.refresh()
            token = self.store.access_token
            response = self._send(method, path, body=body, token=token)

        return self._expect(response)

    def start(
        self,
        device_name: str,
        *,
        new_account: bool = False,
        public_handle: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(device_name, str):
            raise GameClientError("invalid_arguments", "device_name must be a string.")
        name = device_name.strip()
        if not name or len(name) > 64:
            raise GameClientError(
                "invalid_arguments", "device_name must be 1-64 characters."
            )
        body: dict[str, Any] = {
            "device_name": name,
            "new_account": bool(new_account),
        }
        if public_handle is not None:
            if not isinstance(public_handle, str) or len(public_handle) > 32:
                raise GameClientError(
                    "invalid_arguments", "public_handle must be at most 32 characters."
                )
            body["public_handle"] = public_handle
        return self._expect(
            self._send("POST", "/auth/pair/start", body=body)
        )

    def poll_token(self, device_code: str) -> dict[str, Any]:
        if not isinstance(device_code, str) or not device_code.strip():
            raise GameClientError("invalid_grant", "device_code is required.")
        response = self._send(
            "POST",
            "/auth/pair/token",
            body={"device_code": device_code.strip()},
        )
        payload = self._expect(response)
        if isinstance(payload, Mapping):
            self.store.save(payload)
        return dict(payload)

    poll = poll_token
    token = poll_token
    exchange = poll_token

    def approve(self, user_code: str) -> dict[str, Any]:
        code = normalise_user_code(user_code)
        if not code:
            raise GameClientError("invalid_user_code", "user_code is required.")
        return dict(
            self._authorized(
                "POST", "/auth/pair/approve", body={"user_code": code}
            )
        )

    def refresh(self) -> dict[str, Any]:
        session = self.store.load() or {}
        refresh_token = session.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token:
            raise GameClientError(
                "invalid_grant", "No refresh token is available."
            )
        response = self._send(
            "POST", "/auth/refresh", body={"refresh_token": refresh_token}
        )
        if response.status_code == 401:
            self.store.clear()
            raise self._error_from_response(response)
        payload = self._expect(response)
        if isinstance(payload, Mapping):
            self.store.save(payload)
        return dict(payload)

    def list_devices(self) -> dict[str, Any]:
        return dict(self._authorized("GET", "/auth/devices"))

    devices = list_devices

    def revoke(self, device_id: str) -> dict[str, Any]:
        if not isinstance(device_id, str) or not device_id.strip():
            raise GameClientError("invalid_arguments", "device_id is required.")
        value = device_id.strip()
        payload = self._authorized(
            "POST", f"/auth/devices/{quote(value, safe='')}/revoke"
        )
        if self.store.device_id == value:
            self.store.clear()
        return dict(payload)

    revoke_device = revoke

    def logout(self) -> dict[str, Any]:
        payload = self._authorized("POST", "/auth/logout")
        self.store.clear()
        return dict(payload)


__all__ = [
    "DEFAULT_ACCESS_TTL_S",
    "DEFAULT_INTERVAL_S",
    "DEFAULT_PAIRING_TTL_S",
    "DEFAULT_REFRESH_TTL_S",
    "PairingClient",
    "SessionStore",
    "USER_CODE_ALPHABET",
    "data_dir",
    "default_session_path",
    "format_user_code",
    "is_valid_user_code",
    "normalise_user_code",
]
