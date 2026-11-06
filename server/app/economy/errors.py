"""Typed economy failures shared by the service layer and HTTP routes."""

from __future__ import annotations


class EconomyError(Exception):
    """Base class for expected economy failures."""

    code = "economy_error"
    status_code = 400

    def __init__(self, message: str = "Economy operation failed.") -> None:
        super().__init__(message)
        self.message = message


class InvalidAmount(EconomyError):
    code = "invalid_amount"
    status_code = 422


class InvalidSourceEvent(EconomyError):
    code = "invalid_source_event"
    status_code = 422


class SourceEventConflict(EconomyError):
    code = "source_event_conflict"
    status_code = 409


class InsufficientFunds(EconomyError):
    code = "insufficient_funds"
    status_code = 409


class BountyNotFound(EconomyError):
    code = "bounty_not_found"
    status_code = 404


class BountyNotActive(EconomyError):
    code = "bounty_not_active"
    status_code = 409


class BountyNotEligible(EconomyError):
    code = "bounty_not_eligible"
    status_code = 409
