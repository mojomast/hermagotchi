"""Compact LLM-facing JSON schemas for the eight Hermagotchi tools.

The catalog contract is frozen at exactly eight composable tools. New behaviour
must be added as an ``op`` on one of these tools, never as a ninth tool.
"""

from __future__ import annotations

from typing import Any

TOOL_NAMES = (
    "hermagotchi_status",
    "hermagotchi_pet",
    "hermagotchi_goals",
    "hermagotchi_challenge",
    "hermagotchi_battle",
    "hermagotchi_shop",
    "hermagotchi_social",
    "hermagotchi_meta",
)

_IDEMPOTENCY = {
    "type": "string",
    "description": "Client UUID/ULID for mutations.",
}

_SPECIES = {"type": "string", "enum": ["byteblob", "patchfox", "nullgeist"]}
_CARE = {"type": "string", "enum": ["feed", "play", "rest"]}
_MODE = {"type": "string", "enum": ["human", "agent", "co-op"]}
_SLOT = {
    "type": "string",
    "enum": ["head", "face", "back", "front", "aura", "emote", "habitat", "title"],
}


# Honest disclosure: every agent tool runs against an in-memory offline
# practice simulation (``tools.FakeGameClient``), not the hosted game.
SIMULATION_NOTE = "Offline practice sim; resets on restart. "


def _schema(
    description: str,
    ops: list[str],
    properties: dict[str, Any] | None = None,
    *,
    mutating: bool = False,
) -> dict[str, Any]:
    props: dict[str, Any] = {"op": {"type": "string", "enum": ops}}
    props.update(properties or {})
    if mutating:
        props["idempotency_key"] = _IDEMPOTENCY
    return {
        "type": "object",
        "description": SIMULATION_NOTE + description,
        "properties": props,
        "required": ["op"],
        "additionalProperties": False,
    }


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "hermagotchi_status": _schema(
        "Read account, pet, wallet, goal, inbox, health, pairing.",
        ["me", "pet", "wallet", "goal", "inbox", "health", "pair"],
        {
            "user_code": {"type": "string", "maxLength": 9},
            "device_name": {"type": "string", "maxLength": 64},
            "new_account": {"type": "boolean"},
            "revoke_device_id": {"type": "string"},
        },
    ),
    "hermagotchi_pet": _schema(
        "Adopt or rename a pet, set mode, or feed/play/rest.",
        ["adopt", "rename", "set_mode", "care"],
        {
            "species": _SPECIES,
            "name": {"type": "string", "maxLength": 32},
            "mode": _MODE,
            "action": _CARE,
        },
        mutating=True,
    ),
    "hermagotchi_goals": _schema(
        "List, set, or clear an owner-authorized game goal.",
        ["list", "set", "clear"],
        {
            "target_type": {"type": "string", "enum": ["cosmetic", "rank", "achievement"]},
            "target_id": {
                "type": "string",
                "maxLength": 64,
                "description": "Allowlisted catalog item or rank target.",
            },
            "chosen_by": {"type": "string", "enum": ["human", "agent", "co-op"]},
            "spending_limit_bits": {"type": "integer", "minimum": 0},
            "max_battles": {"type": "integer", "minimum": 0},
            "expires_at": {"type": "string", "description": "ISO-8601 UTC."},
        },
        mutating=True,
    ),
    "hermagotchi_challenge": _schema(
        "List opponents, invite, respond, or submit tactics.",
        ["list_opponents", "invite", "respond", "submit_tactics"],
        {
            "opponent_id": {"type": "string"},
            "mode": {"type": "string", "enum": ["practice", "casual", "ranked"]},
            "challenge_id": {"type": "string"},
            "action": {"type": "string", "enum": ["accept", "decline"]},
            "match_id": {"type": "string"},
            "tactics": {"type": "object"},
        },
        mutating=True,
    ),
    "hermagotchi_battle": _schema(
        "Practice against a bot, fetch or replay a match, or claim rewards.",
        ["practice", "get", "replay", "claim"],
        {"match_id": {"type": "string"}},
        mutating=True,
    ),
    "hermagotchi_shop": _schema(
        "Browse catalog, inspect inventory, buy, or equip.",
        ["catalog", "inventory", "buy", "equip"],
        {"item_id": {"type": "string"}, "slot": _SLOT},
        mutating=True,
    ),
    "hermagotchi_social": _schema(
        "Read chat, send messages/DMs, manage friends, read history, block, "
        "report, or taunt.",
        ["read", "send", "block", "report", "inbox", "taunt", "friends", "history"],
        {
            "channel_id": {"type": "string"},
            "body": {"type": "string", "maxLength": 500},
            "target": {
                "type": "string",
                "maxLength": 64,
                "description": "Player or pet name/id.",
            },
            "target_id": {"type": "string"},
            "reason": {"type": "string", "maxLength": 200},
            "match_id": {"type": "string"},
            "phase": {"type": "string", "enum": ["pre", "post"]},
            "lobby": {"type": "boolean"},
            "action": {
                "type": "string",
                "enum": ["list", "add", "accept", "decline", "remove"],
            },
            "filter": {
                "type": "string",
                "enum": ["all", "taunts_sent", "taunts_received", "mentions"],
            },
        },
        mutating=True,
    ),
    "hermagotchi_meta": _schema(
        "Read leaderboard/bounties, or claim a bounty.",
        ["leaderboard", "bounties", "claim_bounty"],
        {"season_id": {"type": "string"}, "bounty_id": {"type": "string"}},
        mutating=True,
    ),
}

# Compatibility aliases for callers that prefer a shorter name.
SCHEMAS = TOOL_SCHEMAS
OP_ENUMS = {name: list(schema["properties"]["op"]["enum"]) for name, schema in TOOL_SCHEMAS.items()}
