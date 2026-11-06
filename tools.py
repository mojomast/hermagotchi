"""Hermagotchi tool handlers backed by an in-memory fake game client.

This slice intentionally performs no network I/O. Every handler returns the
contracts-v1 envelope ``{ok, data, error_code, correlation_id}`` so the fake can
later be replaced by the hosted HTTP client without changing the tool surface.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

try:  # Imported as part of a plugin package.
    from .schemas import OP_ENUMS, TOOL_SCHEMAS
except ImportError:  # Imported from a checkout with the plugin root on sys.path.
    from schemas import OP_ENUMS, TOOL_SCHEMAS

ENVELOPE_KEYS = ("ok", "data", "error_code", "correlation_id")

DEFAULT_POLICY: dict[str, Any] = {
    "mode": "human",
    "network_enabled": False,
    "agent_autonomy_enabled": False,
    "agent_chat_enabled": False,
    "agent_chat_send_per_day": 0,
    "agent_challenges_per_day": 0,
    "agent_ranked_matches_per_day": 0,
    "agent_inference_decisions_per_day": 0,
    "llm_budget_usd_per_day": 0.0,
    "allow_goal_selection": False,
    "allow_cosmetic_purchases": False,
    "require_human_approval_for_ranked": True,
    "quiet_hours_local": ["22:00", "08:00"],
}

MUTATING_OPS: dict[str, set[str]] = {
    "hermagotchi_status": set(),
    "hermagotchi_pet": {"adopt", "rename", "set_mode", "care"},
    "hermagotchi_goals": {"set", "clear"},
    "hermagotchi_challenge": {"invite", "respond", "submit_tactics"},
    "hermagotchi_battle": {"practice", "claim"},
    "hermagotchi_shop": {"buy", "equip"},
    "hermagotchi_social": {"send", "block", "report"},
    "hermagotchi_meta": {"claim_bounty"},
}

SPECIES = ("byteblob", "patchfox", "nullgeist")
MODES = ("human", "agent", "co-op")
CARE_ACTIONS = ("feed", "play", "rest")
SLOTS = ("head", "face", "back", "front", "aura", "emote", "habitat", "title")

CATALOG = (
    {"item_id": "hat.binary_crown", "slot": "head", "rarity": "epic", "price_bits": 1200},
    {"item_id": "face.pixel_visor", "slot": "face", "rarity": "uncommon", "price_bits": 350},
    {"item_id": "back.star_cloak", "slot": "back", "rarity": "rare", "price_bits": 700},
    {"item_id": "aura.glitch_spark", "slot": "aura", "rarity": "common", "price_bits": 150},
)

BOUNTIES = (
    {"bounty_id": "daily.first_care", "reward_bits": 100, "reward_xp": 20},
    {"bounty_id": "daily.practice", "reward_bits": 150, "reward_xp": 30},
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ok(data: Any, correlation_id: str) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "error_code": None,
        "correlation_id": correlation_id,
    }


def _error(code: str, correlation_id: str) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error_code": code,
        "correlation_id": correlation_id,
    }


class FakeGameClient:
    """Small deterministic stand-in for the hosted game API.

    It stores all state in memory. Network-dependent operations respect the
    owner policy and fail with ``network_disabled`` while the default policy has
    networking off. Mutations require an idempotency key and replay the first
    successful receipt for duplicate keys.
    """

    def __init__(self, policy: dict[str, Any] | None = None) -> None:
        self.policy = dict(DEFAULT_POLICY)
        if policy:
            self.policy.update(policy)
        self.pet: dict[str, Any] | None = None
        self.wallet_bits = 0
        self.goal: dict[str, Any] | None = None
        self.ledger: list[dict[str, Any]] = []
        self.inventory: dict[str, dict[str, Any]] = {}
        self.equipment: dict[str, str] = {}
        self.challenges: dict[str, dict[str, Any]] = {}
        self.matches: dict[str, dict[str, Any]] = {}
        self.claimed_bounties: set[str] = set()
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._idempotency: dict[tuple[str, str], dict[str, Any]] = {}
        self._counter = 0

    # -- dispatch ---------------------------------------------------------
    def execute(self, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if tool not in TOOL_SCHEMAS:
            return _error("unknown_tool", self._new_correlation())

        args = dict(arguments or {})
        correlation_id = args.pop("correlation_id", None) or self._new_correlation()
        self.calls.append((tool, dict(args)))

        op = args.get("op")
        if not isinstance(op, str) or op not in OP_ENUMS[tool]:
            return _error("unknown_op", correlation_id)

        mutating = op in MUTATING_OPS[tool]
        idem_key: str | None = None
        if mutating:
            candidate = args.get("idempotency_key")
            if not isinstance(candidate, str) or not candidate.strip():
                return _error("missing_idempotency_key", correlation_id)
            idem_key = candidate.strip()
            receipt = self._idempotency.get((tool, idem_key))
            if receipt is not None:
                return dict(receipt)

        handler = self._handlers().get((tool, op))
        if handler is None:  # Defensive: every contract op has a handler.
            return _error("unknown_op", correlation_id)

        result = handler(args, correlation_id)
        if mutating and idem_key is not None and result["ok"]:
            self._idempotency[(tool, idem_key)] = dict(result)
        return result

    def _handlers(self) -> dict[tuple[str, str], Callable[[dict[str, Any], str], dict[str, Any]]]:
        return {
            ("hermagotchi_status", "me"): self._status_me,
            ("hermagotchi_status", "pet"): self._status_pet,
            ("hermagotchi_status", "wallet"): self._status_wallet,
            ("hermagotchi_status", "goal"): self._status_goal,
            ("hermagotchi_status", "inbox"): self._status_inbox,
            ("hermagotchi_status", "health"): self._status_health,
            ("hermagotchi_pet", "adopt"): self._pet_adopt,
            ("hermagotchi_pet", "rename"): self._pet_rename,
            ("hermagotchi_pet", "set_mode"): self._pet_set_mode,
            ("hermagotchi_pet", "care"): self._pet_care,
            ("hermagotchi_goals", "list"): self._goals_list,
            ("hermagotchi_goals", "set"): self._goals_set,
            ("hermagotchi_goals", "clear"): self._goals_clear,
            ("hermagotchi_challenge", "list_opponents"): self._challenge_list_opponents,
            ("hermagotchi_challenge", "invite"): self._challenge_invite,
            ("hermagotchi_challenge", "respond"): self._challenge_respond,
            ("hermagotchi_challenge", "submit_tactics"): self._challenge_submit_tactics,
            ("hermagotchi_battle", "practice"): self._battle_practice,
            ("hermagotchi_battle", "get"): self._battle_get,
            ("hermagotchi_battle", "replay"): self._battle_replay,
            ("hermagotchi_battle", "claim"): self._battle_claim,
            ("hermagotchi_shop", "catalog"): self._shop_catalog,
            ("hermagotchi_shop", "inventory"): self._shop_inventory,
            ("hermagotchi_shop", "buy"): self._shop_buy,
            ("hermagotchi_shop", "equip"): self._shop_equip,
            ("hermagotchi_social", "read"): self._social_read,
            ("hermagotchi_social", "send"): self._social_send,
            ("hermagotchi_social", "block"): self._social_block,
            ("hermagotchi_social", "report"): self._social_report,
            ("hermagotchi_meta", "leaderboard"): self._meta_leaderboard,
            ("hermagotchi_meta", "bounties"): self._meta_bounties,
            ("hermagotchi_meta", "claim_bounty"): self._meta_claim_bounty,
        }

    # -- helpers ----------------------------------------------------------
    def _new_correlation(self) -> str:
        self._counter += 1
        return f"hg-{self._counter:06d}-{uuid.uuid4().hex[:12]}"

    def _require_network(self, correlation_id: str) -> dict[str, Any] | None:
        if not self.policy.get("network_enabled", False):
            return _error("network_disabled", correlation_id)
        return None

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter:06d}"

    def _policy_view(self) -> dict[str, Any]:
        return {
            "mode": self.policy["mode"],
            "network_enabled": bool(self.policy["network_enabled"]),
            "agent_autonomy_enabled": bool(self.policy["agent_autonomy_enabled"]),
            "agent_chat_enabled": bool(self.policy["agent_chat_enabled"]),
            "allow_goal_selection": bool(self.policy["allow_goal_selection"]),
            "allow_cosmetic_purchases": bool(self.policy["allow_cosmetic_purchases"]),
            "require_human_approval_for_ranked": bool(
                self.policy["require_human_approval_for_ranked"]
            ),
        }

    # -- status -----------------------------------------------------------
    def _status_me(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        return _ok({**self._policy_view(), "fake": True}, cid)

    def _status_pet(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        return _ok({"adopted": self.pet is not None, "pet": self.pet}, cid)

    def _status_wallet(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        return _ok(
            {
                "balance": self.wallet_bits,
                "currency": "bits",
                "ledger": list(self.ledger),
            },
            cid,
        )

    def _status_goal(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        return _ok({"goal": self.goal}, cid)

    def _status_inbox(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        pending = [
            challenge
            for challenge in self.challenges.values()
            if challenge["status"] == "pending"
        ]
        return _ok({"challenges": pending}, cid)

    def _status_health(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        return _ok(
            {
                "status": "ok",
                "fake": True,
                **self._policy_view(),
                "checked_at": _now(),
            },
            cid,
        )

    # -- pet --------------------------------------------------------------
    def _pet_adopt(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        if self.pet is not None:
            return _error("conflict", cid)
        species = args.get("species", "byteblob")
        if species not in SPECIES:
            return _error("invalid_arguments", cid)
        name = args.get("name", "Hermagotchi")
        if not isinstance(name, str) or not (1 <= len(name.strip()) <= 32):
            return _error("invalid_arguments", cid)
        self.pet = {
            "pet_id": self._next_id("pet"),
            "species": species,
            "name": name.strip(),
            "mode": self.policy["mode"],
            "level": 1,
            "xp": 0,
            "care": {"health": 100, "comfort": 100, "hunger": 0, "energy": 100},
            "revision": 1,
            "created_at": _now(),
        }
        return _ok({"pet": self.pet}, cid)

    def _pet_rename(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        if self.pet is None:
            return _error("not_found", cid)
        name = args.get("name")
        if not isinstance(name, str) or not (1 <= len(name.strip()) <= 32):
            return _error("invalid_arguments", cid)
        self.pet["name"] = name.strip()
        self.pet["revision"] += 1
        return _ok({"pet": self.pet}, cid)

    def _pet_set_mode(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        if self.pet is None:
            return _error("not_found", cid)
        mode = args.get("mode")
        if mode not in MODES:
            return _error("invalid_arguments", cid)
        self.policy["mode"] = mode
        self.pet["mode"] = mode
        self.pet["revision"] += 1
        return _ok({"pet": self.pet, "policy": self._policy_view()}, cid)

    def _pet_care(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        if self.pet is None:
            return _error("not_found", cid)
        action = args.get("action")
        if action not in CARE_ACTIONS:
            return _error("invalid_arguments", cid)
        care = self.pet["care"]
        if action == "feed":
            care["hunger"] = max(0, care["hunger"] - 25)
        elif action == "play":
            care["comfort"] = min(100, care["comfort"] + 15)
            care["energy"] = max(0, care["energy"] - 5)
        else:  # rest
            care["energy"] = min(100, care["energy"] + 25)
        self.pet["revision"] += 1
        receipt = {
            "receipt_id": self._next_id("care"),
            "action": action,
            "care": dict(care),
            "pet_revision": self.pet["revision"],
            "at": _now(),
        }
        return _ok({"pet": self.pet, "receipt": receipt}, cid)

    # -- goals ------------------------------------------------------------
    def _goals_list(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        return _ok({"goals": [self.goal] if self.goal else []}, cid)

    def _goals_set(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        target_type = args.get("target_type")
        target_id = args.get("target_id")
        if target_type not in ("cosmetic", "rank", "achievement") or not isinstance(
            target_id, str
        ):
            return _error("invalid_arguments", cid)
        if not (self.policy["allow_goal_selection"] or self.policy["mode"] != "agent"):
            return _error("policy_denied", cid)
        self.goal = {
            "type": target_type,
            "target_id": target_id,
            "chosen_by": self.policy["mode"],
            "chosen_at": _now(),
            "spending_limit_bits": int(args.get("spending_limit_bits", 0)),
            "max_battles": int(args.get("max_battles", 0)),
        }
        return _ok({"goal": self.goal}, cid)

    def _goals_clear(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        self.goal = None
        return _ok({"goal": None, "cleared": True}, cid)

    # -- challenges -------------------------------------------------------
    def _challenge_list_opponents(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        return _ok(
            {
                "opponents": [
                    {"opponent_id": "bot_byteblob", "name": "Training Byteblob"},
                    {"opponent_id": "bot_patchfox", "name": "Training Patchfox"},
                ]
            },
            cid,
        )

    def _challenge_invite(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        opponent_id = args.get("opponent_id")
        mode = args.get("mode", "casual")
        if not isinstance(opponent_id, str) or mode not in ("practice", "casual", "ranked"):
            return _error("invalid_arguments", cid)
        challenge_id = self._next_id("challenge")
        challenge = {
            "challenge_id": challenge_id,
            "opponent_id": opponent_id,
            "mode": mode,
            "status": "pending",
            "created_at": _now(),
        }
        self.challenges[challenge_id] = challenge
        return _ok({"challenge": challenge}, cid)

    def _challenge_respond(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        challenge_id = args.get("challenge_id")
        action = args.get("action")
        challenge = self.challenges.get(challenge_id) if isinstance(challenge_id, str) else None
        if challenge is None:
            return _error("not_found", cid)
        if action not in ("accept", "decline"):
            return _error("invalid_arguments", cid)
        if challenge["status"] != "pending":
            return _error("conflict", cid)
        challenge["status"] = "accepted" if action == "accept" else "declined"
        return _ok({"challenge": challenge}, cid)

    def _challenge_submit_tactics(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        match_id = args.get("match_id")
        tactics = args.get("tactics")
        if not isinstance(tactics, dict) or not isinstance(match_id, str):
            return _error("invalid_arguments", cid)
        actions = tactics.get("actions", [])
        if not isinstance(actions, list) or len(actions) > 4:
            return _error("invalid_arguments", cid)
        match = self.matches.setdefault(
            match_id,
            {"match_id": match_id, "status": "awaiting_tactics", "tactics": {}},
        )
        match["tactics"]["self"] = tactics
        match["status"] = "ready"
        return _ok({"match": match}, cid)

    # -- battle -----------------------------------------------------------
    def _battle_practice(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        if self.pet is None:
            return _error("not_found", cid)
        match_id = self._next_id("match")
        match = {
            "match_id": match_id,
            "mode": "practice",
            "status": "resolved",
            "winner": "self",
            "rounds": 3,
            "reward_bits": 10,
            "reward_xp": 15,
            "claimed": False,
        }
        self.matches[match_id] = match
        return _ok({"match": match}, cid)

    def _battle_get(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        match_id = args.get("match_id")
        match = self.matches.get(match_id) if isinstance(match_id, str) else None
        if match is None:
            return _error("not_found", cid)
        return _ok({"match": match}, cid)

    def _battle_replay(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        match_id = args.get("match_id")
        match = self.matches.get(match_id) if isinstance(match_id, str) else None
        if match is None:
            return _error("not_found", cid)
        replay = {
            "match_id": match_id,
            "ruleset_version": "battle-1",
            "events": [
                {"round": n, "actor": "self" if n % 2 else "bot", "move": "basic_attack"}
                for n in range(1, match.get("rounds", 1) + 1)
            ],
        }
        return _ok({"replay": replay}, cid)

    def _battle_claim(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        match_id = args.get("match_id")
        match = self.matches.get(match_id) if isinstance(match_id, str) else None
        if match is None:
            return _error("not_found", cid)
        if match["status"] != "resolved":
            return _error("conflict", cid)
        if match.get("claimed"):
            return _error("conflict", cid)
        match["claimed"] = True
        self.wallet_bits += int(match.get("reward_bits", 0))
        self.ledger.append(
            {
                "delta": int(match.get("reward_bits", 0)),
                "reason": "battle.practice",
                "source_event_id": match_id,
                "created_at": _now(),
            }
        )
        return _ok(
            {
                "match_id": match_id,
                "reward_bits": match.get("reward_bits", 0),
                "reward_xp": match.get("reward_xp", 0),
                "balance": self.wallet_bits,
            },
            cid,
        )

    # -- shop -------------------------------------------------------------
    def _shop_catalog(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        return _ok({"catalog_version": "fake-1", "items": list(CATALOG)}, cid)

    def _shop_inventory(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        return _ok(
            {
                "items": list(self.inventory.values()),
                "equipment": dict(self.equipment),
            },
            cid,
        )

    def _shop_buy(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        item_id = args.get("item_id")
        item = next((row for row in CATALOG if row["item_id"] == item_id), None)
        if item is None:
            return _error("not_found", cid)
        if item_id in self.inventory:
            return _error("conflict", cid)
        price = int(item["price_bits"])
        if self.wallet_bits < price:
            return _error("insufficient_funds", cid)
        self.wallet_bits -= price
        self.inventory[item_id] = {
            "item_id": item_id,
            "slot": item["slot"],
            "acquired_at": _now(),
        }
        self.ledger.append(
            {
                "delta": -price,
                "reason": "shop.purchase",
                "source_event_id": item_id,
                "created_at": _now(),
            }
        )
        return _ok(
            {"item": self.inventory[item_id], "balance": self.wallet_bits},
            cid,
        )

    def _shop_equip(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        item_id = args.get("item_id")
        slot = args.get("slot")
        owned = self.inventory.get(item_id) if isinstance(item_id, str) else None
        if owned is None:
            return _error("not_found", cid)
        if slot not in SLOTS:
            return _error("invalid_arguments", cid)
        if owned["slot"] != slot:
            return _error("invalid_arguments", cid)
        self.equipment[slot] = item_id
        return _ok(
            {"equipment": dict(self.equipment), "item": owned},
            cid,
        )

    # -- social -----------------------------------------------------------
    def _social_read(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        return _ok({"messages": []}, cid)

    def _social_send(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        channel_id = args.get("channel_id")
        body = args.get("body")
        if not isinstance(channel_id, str) or not isinstance(body, str) or not body.strip():
            return _error("invalid_arguments", cid)
        if len(body) > 500:
            return _error("invalid_arguments", cid)
        return _ok(
            {
                "message": {
                    "message_id": self._next_id("msg"),
                    "channel_id": channel_id,
                    "body": body,
                    "created_at": _now(),
                }
            },
            cid,
        )

    def _social_block(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        target_id = args.get("target_id")
        if not isinstance(target_id, str):
            return _error("invalid_arguments", cid)
        return _ok({"blocked": target_id}, cid)

    def _social_report(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        target_id = args.get("target_id")
        reason = args.get("reason")
        if not isinstance(target_id, str) or not isinstance(reason, str):
            return _error("invalid_arguments", cid)
        return _ok(
            {
                "report": {
                    "report_id": self._next_id("report"),
                    "target_id": target_id,
                    "reason": reason,
                    "status": "received",
                }
            },
            cid,
        )

    # -- meta -------------------------------------------------------------
    def _meta_leaderboard(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        return _ok(
            {
                "season_id": args.get("season_id", "season-1"),
                "entries": [],
            },
            cid,
        )

    def _meta_bounties(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        return _ok(
            {
                "bounties": [
                    {**bounty, "claimed": bounty["bounty_id"] in self.claimed_bounties}
                    for bounty in BOUNTIES
                ]
            },
            cid,
        )

    def _meta_claim_bounty(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        bounty_id = args.get("bounty_id")
        bounty = next((row for row in BOUNTIES if row["bounty_id"] == bounty_id), None)
        if bounty is None:
            return _error("not_found", cid)
        if bounty_id in self.claimed_bounties:
            return _error("conflict", cid)
        self.claimed_bounties.add(bounty_id)
        self.wallet_bits += int(bounty["reward_bits"])
        self.ledger.append(
            {
                "delta": int(bounty["reward_bits"]),
                "reason": "bounty.claim",
                "source_event_id": bounty_id,
                "created_at": _now(),
            }
        )
        return _ok(
            {
                "bounty_id": bounty_id,
                "reward_bits": bounty["reward_bits"],
                "balance": self.wallet_bits,
            },
            cid,
        )


_DEFAULT_CLIENT = FakeGameClient()


def get_default_client() -> FakeGameClient:
    return _DEFAULT_CLIENT


def reset_default_client(client: FakeGameClient | None = None) -> FakeGameClient:
    global _DEFAULT_CLIENT
    _DEFAULT_CLIENT = client or FakeGameClient()
    return _DEFAULT_CLIENT


def _client_from(context: Any) -> FakeGameClient | None:
    if context is None:
        return None
    if isinstance(context, FakeGameClient):
        return context
    client = getattr(context, "client", None)
    return client if isinstance(client, FakeGameClient) else None


def handle_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    client: FakeGameClient | None = None,
    context: Any = None,
) -> dict[str, Any]:
    active = client or _client_from(context) or get_default_client()
    return active.execute(tool_name, arguments)


def _make_handler(tool_name: str) -> Callable[..., dict[str, Any]]:
    def handler(
        arguments: dict[str, Any] | None = None,
        context: Any = None,
        *,
        client: FakeGameClient | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        return handle_tool(tool_name, arguments, client=client, context=context)

    handler.__name__ = f"handle_{tool_name}"
    handler.__doc__ = f"Handle the {tool_name} tool and return the contracts-v1 envelope."
    return handler


HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    name: _make_handler(name) for name in TOOL_SCHEMAS
}
TOOLS = HANDLERS
