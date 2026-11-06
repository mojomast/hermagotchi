"""Error types raised by the Hermagotchi game client."""

from __future__ import annotations

from typing import Any, Mapping


class GameClientError(Exception):
    """A transport, policy, or contracts-v1 API error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 0,
        retry_after_s: int = 0,
        correlation_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = int(status_code)
        self.retry_after_s = int(retry_after_s)
        self.correlation_id = correlation_id
        self.payload = dict(payload or {})

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retry_after_s": self.retry_after_s,
            "correlation_id": self.correlation_id,
        }

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class PolicyDeniedError(GameClientError):
    """The owner policy blocks the requested action."""

    def __init__(self, code: str, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("status_code", 403)
        super().__init__(code, message, **kwargs)
