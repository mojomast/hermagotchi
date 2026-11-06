"""Device-pairing auth endpoints (contracts-v1 addendum, HGT-W7)."""

from __future__ import annotations

import hmac
import math
import sqlite3
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .. import auth
from ..db import get_current_account_id, get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class PairStartRequest(BaseModel):
    device_name: str = Field(min_length=1, max_length=64)
    new_account: bool = False
    public_handle: str | None = Field(default=None, max_length=32)
    model_config = ConfigDict(extra="ignore")

    @field_validator("device_name")
    @classmethod
    def clean_device_name(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 64:
            raise ValueError("device_name must be 1-64 characters")
        return value

    @field_validator("public_handle")
    @classmethod
    def clean_public_handle(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class PairApproveRequest(BaseModel):
    user_code: str = Field(min_length=1, max_length=32)
    model_config = ConfigDict(extra="ignore")


class PairTokenRequest(BaseModel):
    device_code: str = Field(min_length=1, max_length=256)
    model_config = ConfigDict(extra="ignore")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=256)
    model_config = ConfigDict(extra="ignore")


def _error(
    status_code: int,
    code: str,
    message: str,
    *,
    retry_after_s: int = 0,
) -> HTTPException:
    headers = {"Retry-After": str(retry_after_s)} if retry_after_s else None
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "retry_after_s": retry_after_s,
        },
        headers=headers,
    )


def _rate_limited(retry_after_s: int) -> HTTPException:
    return _error(
        429,
        "rate_limited",
        "Too many requests. Try again later.",
        retry_after_s=retry_after_s,
    )


def _limiter(request: Request) -> auth.AuthRateLimiter:
    limiter = getattr(request.app.state, "auth_rate_limiter", None)
    if limiter is None:
        limiter = auth.AuthRateLimiter()
        request.app.state.auth_rate_limiter = limiter
    return limiter


def _client_ip(request: Request) -> str:
    # Respect forwarding headers only when a trusted proxy is declared via
    # HERMAGOTCHI_TRUSTED_PROXY (1/true/yes); otherwise they are untrusted input.
    if auth.trusted_proxy():
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first_hop = forwarded.split(",", 1)[0].strip()
            if first_hop:
                return first_hop
        real_ip = (request.headers.get("x-real-ip") or "").strip()
        if real_ip:
            return real_ip
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def _signup_error(code: str) -> HTTPException:
    if code == "signup_closed":
        return _error(
            403,
            "signup_closed",
            "New account sign-ups are closed right now.",
        )
    return _error(
        403,
        "signup_ip_limit",
        "This network has reached the new-account limit.",
    )


def _require_active_account(conn: sqlite3.Connection, account_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM accounts WHERE id = ? AND status = 'active'",
        (account_id,),
    ).fetchone()
    if row is None:
        raise _error(401, "unauthorized", "A valid account session is required.")


def _unique_user_code(conn: sqlite3.Connection, now_iso: str) -> tuple[str, str]:
    for _ in range(16):
        display = auth.generate_user_code()
        normalized = auth.normalize_user_code(display)
        existing = conn.execute(
            """
            SELECT 1 FROM pairings
            WHERE user_code = ? AND used_at IS NULL AND expires_at > ?
            """,
            (normalized, now_iso),
        ).fetchone()
        if existing is None:
            return display, normalized
    raise _error(503, "unavailable", "Could not allocate a pairing code.")


def _unique_public_handle(
    conn: sqlite3.Connection, requested: str | None, account_id: str
) -> str:
    base = requested or f"pilot_{account_id[-8:]}"
    base = base[:32]
    candidate = base
    for attempt in range(1, 20):
        existing = conn.execute(
            "SELECT 1 FROM accounts WHERE public_handle = ?", (candidate,)
        ).fetchone()
        if existing is None:
            return candidate
        suffix = f"_{attempt}"
        candidate = f"{base[: 32 - len(suffix)]}{suffix}"
    suffix = f"_{account_id[:8]}"
    return f"{base[: 32 - len(suffix)]}{suffix}"


def _create_account(
    conn: sqlite3.Connection,
    public_handle: str | None,
    now_iso: str,
    client_ip: str,
) -> str:
    limit_code = auth.signup_limit_code(conn, client_ip)
    if limit_code is not None:
        raise _signup_error(limit_code)

    account_id = str(uuid.uuid4())
    handle = _unique_public_handle(conn, public_handle, account_id)
    conn.execute(
        """
        INSERT INTO accounts (id, public_handle, status, created_at, privacy_flags, created_ip)
        VALUES (?, ?, 'active', ?, '{}', ?)
        """,
        (account_id, handle, now_iso, client_ip),
    )
    conn.execute(
        """
        INSERT INTO signup_ip_stats (ip, signup_count, first_signup_at, last_signup_at)
        VALUES (?, 1, ?, ?)
        ON CONFLICT(ip) DO UPDATE SET
            signup_count = signup_ip_stats.signup_count + 1,
            last_signup_at = excluded.last_signup_at
        """,
        (client_ip, now_iso, now_iso),
    )
    return account_id


def _issue_tokens(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    device_id: str,
    now: float,
) -> dict[str, Any]:
    access_token = auth.new_token(auth.ACCESS_TOKEN_PREFIX)
    refresh_token = auth.new_token(auth.REFRESH_TOKEN_PREFIX)
    access_ttl = auth.access_ttl_s()
    refresh_ttl = auth.refresh_ttl_s()
    now_iso = auth.iso_from_ts(now)

    conn.execute(
        """
        INSERT INTO auth_sessions (
            id, device_id, account_id, access_token_hash, refresh_token_hash,
            created_at, access_expires_at, refresh_expires_at, last_used_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            device_id,
            account_id,
            auth.hash_token(access_token),
            auth.hash_token(refresh_token),
            now_iso,
            auth.iso_from_ts(now + access_ttl),
            auth.iso_from_ts(now + refresh_ttl),
            now_iso,
        ),
    )
    conn.execute(
        "UPDATE devices SET last_seen_at = ? WHERE id = ?",
        (now_iso, device_id),
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": access_ttl,
        "refresh_expires_in": refresh_ttl,
        "account_id": account_id,
        "device_id": device_id,
    }


def _revoke_device(conn: sqlite3.Connection, device_id: str, now: float) -> None:
    stamp = auth.iso_from_ts(now)
    with conn:
        conn.execute(
            "UPDATE devices SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
            (stamp, device_id),
        )
        conn.execute(
            """
            UPDATE auth_sessions SET revoked_at = ?
            WHERE device_id = ? AND revoked_at IS NULL
            """,
            (stamp, device_id),
        )


def _current_device_id(
    conn: sqlite3.Connection, request: Request, account_id: str
) -> str | None:
    token = auth.bearer_token(request.headers.get("Authorization"))
    if not token:
        return None
    row = conn.execute(
        """
        SELECT device_id, account_id FROM auth_sessions
        WHERE access_token_hash = ?
        """,
        (auth.hash_token(token),),
    ).fetchone()
    if row is None or row["account_id"] != account_id:
        return None
    return str(row["device_id"])


@router.post("/pair/start", status_code=201)
def start_pairing(
    payload: PairStartRequest,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    limiter = _limiter(request)
    allowed, retry_after_s = limiter.allow(
        f"pair_start:{_client_ip(request)}",
        auth.PAIR_START_LIMIT,
        auth.PAIR_START_WINDOW_S,
    )
    if not allowed:
        raise _rate_limited(retry_after_s)

    if payload.new_account:
        limit_code = auth.signup_limit_code(conn, _client_ip(request))
        if limit_code is not None:
            raise _signup_error(limit_code)

    now = auth.now_ts()
    created_at = auth.iso_from_ts(now)
    expires_at = auth.iso_from_ts(now + auth.pairing_ttl_s())
    display_code, normalized_code = _unique_user_code(conn, expires_at)
    device_code = auth.new_token(auth.DEVICE_CODE_PREFIX)

    conn.execute(
        """
        INSERT INTO pairings (
            id, device_code_hash, user_code, device_name, new_account,
            public_handle, created_at, expires_at, approved_at, interval_s
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            auth.hash_token(device_code),
            normalized_code,
            payload.device_name,
            1 if payload.new_account else 0,
            payload.public_handle,
            created_at,
            expires_at,
            created_at if payload.new_account else None,
            auth.poll_interval_s(),
        ),
    )
    conn.commit()

    return {
        "device_code": device_code,
        "user_code": display_code,
        "expires_at": expires_at,
        "interval_s": auth.poll_interval_s(),
        "new_account": payload.new_account,
    }


@router.post("/pair/approve")
def approve_pairing(
    payload: PairApproveRequest,
    request: Request,
    account_id: str = Depends(get_current_account_id),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_active_account(conn, account_id)
    now = auth.now_ts()
    normalized = auth.normalize_user_code(payload.user_code)
    limiter = _limiter(request)
    ip_key = f"approve_ip:{_client_ip(request)}"

    if limiter.is_locked(normalized, now) or limiter.is_locked(ip_key, now):
        raise _rate_limited(auth.pairing_ttl_s())

    row = conn.execute(
        """
        SELECT * FROM pairings
        WHERE user_code = ?
        ORDER BY created_at DESC
        """,
        (normalized,),
    ).fetchone()
    if row is None:
        limiter.record_failure(normalized, now=now)
        limiter.record_failure(ip_key, now=now)
        raise _error(404, "invalid_user_code", "That pairing code is not valid.")

    if row["used_at"] is not None:
        raise _error(409, "already_used", "That pairing code was already used.")

    if auth.ts_from_iso(row["expires_at"]) <= now:
        raise _error(400, "expired_token", "That pairing code has expired.")

    if row["approved_at"] is not None:
        if row["approved_account_id"] not in (None, account_id):
            raise _error(409, "already_used", "That pairing code was already approved.")
    else:
        with conn:
            conn.execute(
                """
                UPDATE pairings SET approved_at = ?, approved_account_id = ?
                WHERE id = ? AND approved_at IS NULL
                """,
                (auth.iso_from_ts(now), account_id, row["id"]),
            )
    limiter.clear_failures(normalized)
    limiter.clear_failures(ip_key)

    return {"approved": True, "device_name": row["device_name"]}


@router.post("/pair/token")
def exchange_pairing(
    payload: PairTokenRequest,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    now = auth.now_ts()
    digest = auth.hash_token(payload.device_code)
    row = conn.execute(
        """
        SELECT * FROM pairings
        WHERE device_code_hash = ?
        ORDER BY created_at DESC
        """,
        (digest,),
    ).fetchone()
    if row is None or not hmac.compare_digest(str(row["device_code_hash"]), digest):
        raise _error(400, "invalid_grant", "That device code is not valid.")
    if row["used_at"] is not None:
        raise _error(400, "invalid_grant", "That device code was already exchanged.")
    if auth.ts_from_iso(row["expires_at"]) <= now:
        raise _error(400, "expired_token", "That device code has expired.")

    interval_s = int(row["interval_s"] or auth.poll_interval_s())
    last_poll_at = row["last_poll_at"]
    if last_poll_at is not None:
        elapsed = now - auth.ts_from_iso(last_poll_at)
        if elapsed < interval_s:
            with conn:
                conn.execute(
                    "UPDATE pairings SET last_poll_at = ? WHERE id = ?",
                    (auth.iso_from_ts(now), row["id"]),
                )
            retry_after_s = max(1, int(math.ceil(interval_s - elapsed)))
            raise _error(
                429,
                "slow_down",
                "Polling too quickly. Increase the polling interval.",
                retry_after_s=retry_after_s,
            )

    if row["approved_at"] is None:
        with conn:
            conn.execute(
                "UPDATE pairings SET last_poll_at = ? WHERE id = ?",
                (auth.iso_from_ts(now), row["id"]),
            )
        raise _error(400, "authorization_pending", "This pairing is not approved yet.")

    now_iso = auth.iso_from_ts(now)
    with conn:
        account_id = row["approved_account_id"]
        if account_id is None:
            if not row["new_account"]:
                raise _error(400, "invalid_grant", "That device code is not approved.")
            account_id = _create_account(
                conn,
                row["public_handle"],
                now_iso,
                _client_ip(request),
            )

        device_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO devices (
                id, account_id, device_name, created_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (device_id, account_id, row["device_name"], now_iso, now_iso),
        )
        tokens = _issue_tokens(
            conn,
            account_id=str(account_id),
            device_id=device_id,
            now=now,
        )
        conn.execute(
            "UPDATE pairings SET used_at = ?, last_poll_at = ? WHERE id = ?",
            (now_iso, now_iso, row["id"]),
        )
    return tokens


@router.post("/refresh")
def refresh_tokens(
    payload: RefreshRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    now = auth.now_ts()
    digest = auth.hash_token(payload.refresh_token)
    row = conn.execute(
        """
        SELECT
            s.*,
            d.revoked_at AS device_revoked_at,
            a.status AS account_status
        FROM auth_sessions AS s
        JOIN devices AS d ON d.id = s.device_id
        JOIN accounts AS a ON a.id = s.account_id
        WHERE s.refresh_token_hash = ?
        """,
        (digest,),
    ).fetchone()
    if row is None or not hmac.compare_digest(str(row["refresh_token_hash"]), digest):
        raise _error(401, "invalid_grant", "That refresh token is not valid.")

    if row["rotated_at"] is not None:
        _revoke_device(conn, str(row["device_id"]), now)
        raise _error(401, "invalid_grant", "That refresh token was already used.")

    if row["revoked_at"] is not None or row["device_revoked_at"] is not None:
        raise _error(401, "invalid_grant", "That refresh token was revoked.")
    if row["account_status"] != "active":
        raise _error(401, "invalid_grant", "That refresh token is not valid.")
    if auth.ts_from_iso(row["refresh_expires_at"]) <= now:
        raise _error(400, "expired_token", "That refresh token has expired.")

    stamp = auth.iso_from_ts(now)
    with conn:
        conn.execute(
            "UPDATE auth_sessions SET rotated_at = ?, revoked_at = ? WHERE id = ?",
            (stamp, stamp, row["id"]),
        )
        tokens = _issue_tokens(
            conn,
            account_id=str(row["account_id"]),
            device_id=str(row["device_id"]),
            now=now,
        )
    return tokens


@router.get("/devices")
def list_devices(
    request: Request,
    account_id: str = Depends(get_current_account_id),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    _require_active_account(conn, account_id)
    current_device_id = _current_device_id(conn, request, account_id)
    rows = conn.execute(
        """
        SELECT id, device_name, created_at, last_seen_at, revoked_at
        FROM devices
        WHERE account_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (account_id,),
    ).fetchall()
    return {
        "devices": [
            {
                "device_id": row["id"],
                "device_name": row["device_name"],
                "created_at": row["created_at"],
                "last_seen_at": row["last_seen_at"],
                "current": row["id"] == current_device_id,
                "revoked": row["revoked_at"] is not None,
            }
            for row in rows
        ]
    }


@router.post("/devices/{device_id}/revoke")
def revoke_device(
    device_id: str,
    account_id: str = Depends(get_current_account_id),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, bool]:
    _require_active_account(conn, account_id)
    row = conn.execute(
        "SELECT id FROM devices WHERE id = ? AND account_id = ?",
        (device_id, account_id),
    ).fetchone()
    if row is None:
        raise _error(404, "not_found", "No device exists for that id.")

    _revoke_device(conn, device_id, auth.now_ts())
    return {"revoked": True}


@router.post("/logout")
def logout(
    request: Request,
    account_id: str = Depends(get_current_account_id),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, bool]:
    _require_active_account(conn, account_id)
    device_id = _current_device_id(conn, request, account_id)
    if device_id is None:
        raise _error(401, "unauthorized", "A valid account session is required.")

    _revoke_device(conn, device_id, auth.now_ts())
    return {"revoked": True}
