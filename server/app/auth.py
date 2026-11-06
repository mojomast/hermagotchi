"""Device-pairing auth primitives: tokens, hashes, modes and rate limiting.

Raw bearer, refresh and device codes are generated here and never stored. Only
their SHA-256 hex digests are written to SQLite. Callers must treat the raw
values as secrets and keep them out of logs and tool output.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import os
import secrets
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ23456789"
USER_CODE_LENGTH = 8

ACCESS_TOKEN_PREFIX = "hga_"
REFRESH_TOKEN_PREFIX = "hgr_"
DEVICE_CODE_PREFIX = "hgd_"

DEFAULT_PAIRING_TTL_S = 600
DEFAULT_ACCESS_TTL_S = 3600
DEFAULT_REFRESH_TTL_S = 30 * 24 * 60 * 60
DEFAULT_POLL_INTERVAL_S = 5

PAIR_START_LIMIT = 10
PAIR_START_WINDOW_S = 60
APPROVE_FAILURE_LIMIT = 5

DEFAULT_SIGNUP_CAP = 100
DEFAULT_SIGNUP_PER_IP = 5
TRUSTED_PROXY_VALUES = {"1", "true", "yes"}


def now_ts() -> float:
    """Current unix time. Tests may monkeypatch this function."""
    return time.time()


def iso_from_ts(value: float) -> str:
    return (
        datetime.fromtimestamp(value, timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def ts_from_iso(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def auth_mode() -> str:
    """Resolve the auth mode at call time so tests can monkeypatch the env."""
    mode = os.environ.get("HERMAGOTCHI_AUTH_MODE", "dev").strip().lower()
    return "production" if mode == "production" else "dev"


def _env_int(names: tuple[str, ...], default: int) -> int:
    for name in names:
        raw = os.environ.get(name)
        if raw is None:
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return default


def pairing_ttl_s() -> int:
    return _env_int(
        ("HERMAGOTCHI_PAIRING_TTL_S", "HERMAGOTCHI_PAIRING_TTL_SECONDS", "HERMAGOTCHI_PAIRING_TTL"),
        DEFAULT_PAIRING_TTL_S,
    )


def access_ttl_s() -> int:
    return _env_int(
        ("HERMAGOTCHI_ACCESS_TTL_S", "HERMAGOTCHI_ACCESS_TTL_SECONDS", "HERMAGOTCHI_ACCESS_TTL"),
        DEFAULT_ACCESS_TTL_S,
    )


def refresh_ttl_s() -> int:
    return _env_int(
        ("HERMAGOTCHI_REFRESH_TTL_S", "HERMAGOTCHI_REFRESH_TTL_SECONDS", "HERMAGOTCHI_REFRESH_TTL"),
        DEFAULT_REFRESH_TTL_S,
    )


def poll_interval_s() -> int:
    return _env_int(
        ("HERMAGOTCHI_POLL_INTERVAL_S", "HERMAGOTCHI_POLL_INTERVAL_SECONDS", "HERMAGOTCHI_POLL_INTERVAL"),
        DEFAULT_POLL_INTERVAL_S,
    )


def _env_nonnegative_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


def signup_cap() -> int:
    """Maximum number of account rows (default 100). Resolved per call."""
    return _env_nonnegative_int("HERMAGOTCHI_SIGNUP_CAP", DEFAULT_SIGNUP_CAP)


def signup_per_ip() -> int:
    """Maximum new accounts created from one client IP (default 5)."""
    return _env_nonnegative_int("HERMAGOTCHI_SIGNUP_PER_IP", DEFAULT_SIGNUP_PER_IP)


def trusted_proxy() -> bool:
    """Whether X-Forwarded-For / X-Real-IP may supply the client IP.

    Only enable HERMAGOTCHI_TRUSTED_PROXY (1/true/yes) when a trusted reverse
    proxy in front of the API overwrites those headers.
    """
    raw = os.environ.get("HERMAGOTCHI_TRUSTED_PROXY", "").strip().lower()
    return raw in TRUSTED_PROXY_VALUES


def signup_account_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS count FROM accounts").fetchone()
    if row is None:
        return 0
    return int(row["count"] or 0)


def signup_ip_count(conn: sqlite3.Connection, ip: str) -> int:
    row = conn.execute(
        "SELECT signup_count FROM signup_ip_stats WHERE ip = ?",
        (ip,),
    ).fetchone()
    if row is None:
        return 0
    return int(row["signup_count"] or 0)


def signup_limit_code(conn: sqlite3.Connection, ip: str) -> str | None:
    """Return the 403 error code for a closed signup channel, else ``None``."""
    if signup_account_count(conn) >= signup_cap():
        return "signup_closed"
    if signup_ip_count(conn, ip) >= signup_per_ip():
        return "signup_ip_limit"
    return None


def new_token(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), stored_hash)


def generate_user_code() -> str:
    compact = "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(USER_CODE_LENGTH))
    return f"{compact[:4]}-{compact[4:]}"


def normalize_user_code(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch not in "- ")


def bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def resolve_session(conn, token: str | None) -> str | None:
    """Resolve a raw access token to its account id, updating last-seen times."""
    if not token:
        return None

    digest = hash_token(token)
    row = conn.execute(
        """
        SELECT
            s.id AS session_id,
            s.account_id,
            s.access_token_hash,
            s.access_expires_at,
            s.revoked_at AS session_revoked_at,
            s.rotated_at,
            d.id AS device_id,
            d.revoked_at AS device_revoked_at,
            a.status AS account_status
        FROM auth_sessions AS s
        JOIN devices AS d ON d.id = s.device_id
        JOIN accounts AS a ON a.id = s.account_id
        WHERE s.access_token_hash = ?
        """,
        (digest,),
    ).fetchone()
    if row is None:
        return None
    if not hmac.compare_digest(str(row["access_token_hash"]), digest):
        return None
    if row["session_revoked_at"] or row["device_revoked_at"] or row["rotated_at"]:
        return None
    if row["account_status"] != "active":
        return None
    if ts_from_iso(row["access_expires_at"]) <= now_ts():
        return None

    stamp = iso_from_ts(now_ts())
    conn.execute(
        "UPDATE auth_sessions SET last_used_at = ? WHERE id = ?",
        (stamp, row["session_id"]),
    )
    conn.execute(
        "UPDATE devices SET last_seen_at = ? WHERE id = ?",
        (stamp, row["device_id"]),
    )
    conn.commit()
    return str(row["account_id"])


@contextmanager
def _db_write(conn: sqlite3.Connection) -> Iterator[None]:
    """Own a SQLite write transaction, or join one already in progress."""
    started_here = not conn.in_transaction
    if started_here:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        if started_here:
            conn.rollback()
        raise
    else:
        if started_here:
            conn.commit()


@dataclass
class AuthRateLimiter:
    """Auth limiter with an optional SQLite-backed store.

    Pass ``conn`` from a route to persist hits and locks in the shared app
    database so every uvicorn worker observes the same state. Without ``conn``
    the limiter keeps the original in-process behaviour (handy for local tests
    and callers that do not have a database handle).
    """

    hits: dict[str, list[float]] = field(default_factory=dict)
    failures: dict[str, int] = field(default_factory=dict)
    locks: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def allow(
        self,
        key: str,
        limit: int,
        window_s: float,
        now: float | None = None,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[bool, int]:
        moment = now_ts() if now is None else now
        if conn is not None:
            return self._allow_db(conn, key, limit, window_s, moment)
        with self._lock:
            bucket = [stamp for stamp in self.hits.get(key, []) if stamp > moment - window_s]
            if len(bucket) >= limit:
                oldest = min(bucket)
                retry = max(1, int(math.ceil(window_s - (moment - oldest))))
                self.hits[key] = bucket
                return False, retry
            bucket.append(moment)
            self.hits[key] = bucket
            return True, 0

    @staticmethod
    def _allow_db(
        conn: sqlite3.Connection,
        key: str,
        limit: int,
        window_s: float,
        moment: float,
    ) -> tuple[bool, int]:
        with _db_write(conn):
            cutoff = moment - window_s
            conn.execute(
                "DELETE FROM auth_rate_hits WHERE key = ? AND stamped_at <= ?",
                (key, cutoff),
            )
            rows = conn.execute(
                "SELECT stamped_at FROM auth_rate_hits WHERE key = ? ORDER BY stamped_at",
                (key,),
            ).fetchall()
            if len(rows) >= limit:
                oldest = float(rows[0][0])
                retry = max(1, int(math.ceil(window_s - (moment - oldest))))
                return False, retry
            conn.execute(
                "INSERT INTO auth_rate_hits (key, stamped_at) VALUES (?, ?)",
                (key, moment),
            )
            return True, 0

    def is_locked(
        self,
        key: str,
        now: float | None = None,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> bool:
        moment = now_ts() if now is None else now
        if conn is not None:
            return self._is_locked_db(conn, key, moment)
        with self._lock:
            until = self.locks.get(key)
            if until is None:
                return False
            if until <= moment:
                self.locks.pop(key, None)
                self.failures.pop(key, None)
                return False
            return True

    @staticmethod
    def _is_locked_db(
        conn: sqlite3.Connection, key: str, moment: float
    ) -> bool:
        with _db_write(conn):
            row = conn.execute(
                "SELECT until_at FROM auth_rate_locks WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return False
            until = float(row[0])
            if until <= 0:
                # A failure counter that has not reached the lock threshold.
                return False
            if until <= moment:
                conn.execute("DELETE FROM auth_rate_locks WHERE key = ?", (key,))
                return False
            return True

    def record_failure(
        self,
        key: str,
        *,
        limit: int = APPROVE_FAILURE_LIMIT,
        lock_for_s: float | None = None,
        now: float | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> bool:
        moment = now_ts() if now is None else now
        duration = pairing_ttl_s() if lock_for_s is None else lock_for_s
        if conn is not None:
            return self._record_failure_db(conn, key, limit, duration, moment)
        with self._lock:
            count = self.failures.get(key, 0) + 1
            self.failures[key] = count
            if count >= limit:
                self.locks[key] = moment + duration
                return True
            return False

    @staticmethod
    def _record_failure_db(
        conn: sqlite3.Connection,
        key: str,
        limit: int,
        duration: float,
        moment: float,
    ) -> bool:
        with _db_write(conn):
            row = conn.execute(
                "SELECT failure_count FROM auth_rate_locks WHERE key = ?", (key,)
            ).fetchone()
            count = (int(row[0]) if row is not None else 0) + 1
            until = 0.0
            locked = False
            if count >= limit:
                until = moment + duration
                locked = True
            conn.execute(
                """
                INSERT INTO auth_rate_locks (key, until_at, failure_count)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    until_at = excluded.until_at,
                    failure_count = excluded.failure_count
                """,
                (key, until, count),
            )
            return locked

    def clear_failures(
        self,
        key: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            with _db_write(conn):
                conn.execute("DELETE FROM auth_rate_locks WHERE key = ?", (key,))
            return
        with self._lock:
            self.failures.pop(key, None)
            self.locks.pop(key, None)


def generate_token(prefix: str = ACCESS_TOKEN_PREFIX) -> str:
    """Compatibility alias for token generation."""
    return new_token(prefix)


RateLimiter = AuthRateLimiter
