"""SQLite connection, migration runner and the injectable test-auth stub."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from . import auth

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
DEFAULT_DB_PATH = "hermagotchi.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.stem in applied:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (path.stem, utc_now_iso()),
        )
    conn.commit()


def init_db(db_path: str | Path) -> Path:
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        migrate(conn)
    finally:
        conn.close()
    return path


def seed_account(conn: sqlite3.Connection, account_id: str, public_handle: str | None = None) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO accounts (id, public_handle, status, created_at, privacy_flags)
        VALUES (?, ?, 'active', ?, '{}')
        """,
        (account_id, public_handle or f"pilot_{account_id[-8:]}", utc_now_iso()),
    )
    conn.commit()


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


def account_exists(conn: sqlite3.Connection, account_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM accounts WHERE id = ? AND status = 'active'",
        (account_id,),
    ).fetchone()
    return row is not None


def _unauthorized(message: str = "A valid account session is required.") -> HTTPException:
    return HTTPException(status_code=401, detail={"code": "unauthorized", "message": message})


def _dev_stub_account_id(
    x_account_id: str | None, token: str | None
) -> str | None:
    candidate = (x_account_id or "").strip() or (token or "").strip()
    if not candidate:
        return None
    try:
        uuid.UUID(candidate)
    except ValueError as exc:
        raise _unauthorized() from exc
    return candidate


def get_current_account_id(
    request: Request,
    x_account_id: Annotated[str | None, Header(alias="X-Account-Id")] = None,
    authorization: Annotated[str | None, Header()] = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> str:
    """Resolve the caller account according to HERMAGOTCHI_AUTH_MODE.

    ``production`` ignores ``X-Account-Id`` completely and accepts only a
    session access token resolved against ``auth_sessions``. ``dev`` tries the
    session token first and then falls back to the historical UUID stub.
    Tests can also inject their own callable through
    ``create_app(auth_dependency=...)`` or FastAPI ``dependency_overrides``.
    """
    token = auth.bearer_token(authorization)

    if auth.auth_mode() == "production":
        account_id = auth.resolve_session(conn, token)
        if account_id is None:
            raise _unauthorized()
        return account_id

    if token:
        account_id = auth.resolve_session(conn, token)
        if account_id is not None:
            return account_id

    account_id = _dev_stub_account_id(x_account_id, token)
    if account_id is None:
        raise _unauthorized()
    return account_id


def get_current_account_id_optional(
    request: Request,
    x_account_id: Annotated[str | None, Header(alias="X-Account-Id")] = None,
    authorization: Annotated[str | None, Header()] = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> str | None:
    """Optional variant for public projections such as the leaderboard.

    Missing credentials yield ``None``; present but invalid credentials still
    fail closed with 401 in both dev and production modes.
    """
    token = auth.bearer_token(authorization)
    if auth.auth_mode() == "production":
        if token is None:
            return None
    elif not (x_account_id or "").strip() and token is None:
        return None

    return get_current_account_id(
        request=request,
        x_account_id=x_account_id,
        authorization=authorization,
        conn=conn,
    )
