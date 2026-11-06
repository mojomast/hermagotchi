"""Typed shop failures shared by the service layer and HTTP routes."""

from __future__ import annotations


class ShopError(Exception):
    """Base class for expected shop failures."""

    code = "shop_error"
    status_code = 400

    def __init__(self, message: str = "Shop operation failed.") -> None:
        super().__init__(message)
        self.message = message

    def to_detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class InvalidIdempotencyKey(ShopError):
    code = "idempotency_key_required"
    status_code = 422


class IdempotencyConflict(ShopError):
    code = "idempotency_conflict"
    status_code = 409


class ItemNotFound(ShopError):
    code = "item_not_found"
    status_code = 404


class ItemInactive(ShopError):
    code = "item_inactive"
    status_code = 409


class ItemAlreadyOwned(ShopError):
    code = "item_already_owned"
    status_code = 409


class ItemNotOwned(ShopError):
    code = "item_not_owned"
    status_code = 403


class ItemIncompatible(ShopError):
    code = "item_incompatible"
    status_code = 409


class SlotIncompatible(ShopError):
    code = "slot_incompatible"
    status_code = 409


class PetNotFound(ShopError):
    code = "pet_not_found"
    status_code = 404


class PetNotOwned(ShopError):
    code = "pet_not_owned"
    status_code = 403
