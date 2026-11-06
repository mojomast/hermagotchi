"""Authoritative Bits economy: wallet projection, ledger and rewards."""

from __future__ import annotations

from .bounties import claim_bounty, list_bounties
from .errors import (
    BountyNotActive,
    BountyNotEligible,
    BountyNotFound,
    EconomyError,
    InsufficientFunds,
    InvalidAmount,
    InvalidSourceEvent,
    SourceEventConflict,
)
from .ledger import (
    PRACTICE_DAILY_REWARD_LIMIT,
    PRACTICE_WEEKLY_BITS_LIMIT,
    PVP_DAILY_REWARD_LIMIT,
    PVP_OPPONENT_DAILY_REWARD_LIMIT,
    count_practice_rewards_today,
    count_pvp_opponent_rewarded_today,
    count_pvp_rewarded_today,
    credit,
    debit,
    ensure_wallet,
    ledger_sum,
    practice_bits_this_week,
    wallet_allowances,
    wallet_payload,
    wallet_reconciles,
)
from .rewards import grant_entitlement, income_allowances

__all__ = [
    "BountyNotActive",
    "BountyNotEligible",
    "BountyNotFound",
    "EconomyError",
    "InsufficientFunds",
    "InvalidAmount",
    "InvalidSourceEvent",
    "PRACTICE_DAILY_REWARD_LIMIT",
    "PRACTICE_WEEKLY_BITS_LIMIT",
    "PVP_DAILY_REWARD_LIMIT",
    "PVP_OPPONENT_DAILY_REWARD_LIMIT",
    "SourceEventConflict",
    "claim_bounty",
    "count_practice_rewards_today",
    "count_pvp_opponent_rewarded_today",
    "count_pvp_rewarded_today",
    "credit",
    "debit",
    "ensure_wallet",
    "grant_entitlement",
    "income_allowances",
    "ledger_sum",
    "list_bounties",
    "practice_bits_this_week",
    "wallet_allowances",
    "wallet_payload",
    "wallet_reconciles",
]
