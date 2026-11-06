"""FastAPI application factory for the contracts-v1 hosted game API."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import CONTRACTS_VERSION
from .db import (
    DEFAULT_DB_PATH,
    connect,
    get_current_account_id,
    init_db,
    seed_account,
)
from .routes.health import router as health_router
from .routes.me import router as me_router
from .routes.pets import router as pets_router


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "corr_unknown")


def create_app(
    db_path: str | Path | None = None,
    seed_account_ids: Iterable[str] = (),
    auth_dependency: Callable[..., str] | None = None,
) -> FastAPI:
    resolved_db = Path(db_path or os.environ.get("HERMAGOTCHI_DB", DEFAULT_DB_PATH))
    resolved_db = init_db(resolved_db)

    app = FastAPI(
        title="Hermagotchi Game API",
        version=CONTRACTS_VERSION,
        docs_url="/v1/docs",
        openapi_url="/v1/openapi.json",
    )
    app.state.db_path = str(resolved_db)

    if seed_account_ids:
        conn = connect(resolved_db)
        try:
            for account_id in seed_account_ids:
                seed_account(conn, account_id)
        finally:
            conn.close()

    if auth_dependency is not None:
        app.dependency_overrides[get_current_account_id] = auth_dependency

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-Id") or f"corr_{uuid.uuid4().hex}"
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers.setdefault("X-Correlation-Id", correlation_id)
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            code = str(detail.get("code") or "http_error")
            message = str(detail.get("message") or "Request failed.")
            retry_after_s = int(detail.get("retry_after_s") or 0)
        else:
            code = {401: "unauthorized", 404: "not_found", 409: "conflict"}.get(
                exc.status_code, "http_error"
            )
            message = str(detail)
            retry_after_s = 0
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": code,
                "message": message,
                "retry_after_s": retry_after_s,
                "correlation_id": _correlation_id(request),
            },
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "Request does not match the contracts-v1 schema.",
                "retry_after_s": 0,
                "correlation_id": _correlation_id(request),
            },
        )

    app.include_router(health_router, prefix="/v1")
    app.include_router(me_router, prefix="/v1")
    app.include_router(pets_router, prefix="/v1")
    return app
