"""Readiness probe. No private details."""

from fastapi import APIRouter

from .. import CONTRACTS_VERSION

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "hermagotchi",
        "contracts_version": CONTRACTS_VERSION,
    }
