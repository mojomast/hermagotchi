"""Expected social/moderation failures shared by services and HTTP routes."""

from __future__ import annotations


class SocialError(Exception):
    """Base class for expected social failures."""

    code = "social_error"
    status_code = 400

    def __init__(self, message: str = "Social operation failed.", *, retry_after_s: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after_s = max(0, int(retry_after_s))

    def to_detail(self) -> dict[str, object]:
        detail: dict[str, object] = {"code": self.code, "message": self.message}
        if self.retry_after_s:
            detail["retry_after_s"] = self.retry_after_s
        return detail


class InvalidChannel(SocialError):
    code = "invalid_channel"
    status_code = 422


class InvalidTarget(SocialError):
    code = "invalid_target"
    status_code = 422


class EmptyMessage(SocialError):
    code = "empty_message"
    status_code = 422


class MessageTooLong(SocialError):
    code = "message_too_long"
    status_code = 422


class RateLimited(SocialError):
    code = "rate_limited"
    status_code = 429


class BlockedInteraction(SocialError):
    code = "blocked"
    status_code = 403
