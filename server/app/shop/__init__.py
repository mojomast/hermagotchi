"""Shop domain: catalog projection, atomic purchases and equipment."""

from __future__ import annotations

from .catalog import get_item, item_payload, list_catalog
from .equipment import equip_item, loadout_for_pet
from .errors import (
    IdempotencyConflict,
    InvalidIdempotencyKey,
    ItemAlreadyOwned,
    ItemInactive,
    ItemIncompatible,
    ItemNotFound,
    ItemNotOwned,
    PetNotFound,
    PetNotOwned,
    ShopError,
    SlotIncompatible,
)
from .purchases import purchase_item

__all__ = [
    "IdempotencyConflict",
    "InvalidIdempotencyKey",
    "ItemAlreadyOwned",
    "ItemInactive",
    "ItemIncompatible",
    "ItemNotFound",
    "ItemNotOwned",
    "PetNotFound",
    "PetNotOwned",
    "ShopError",
    "SlotIncompatible",
    "equip_item",
    "get_item",
    "item_payload",
    "list_catalog",
    "loadout_for_pet",
    "purchase_item",
]
