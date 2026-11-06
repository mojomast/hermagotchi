"""Hermagotchi tool handlers backed by an in-memory fake game client.

This slice intentionally performs no network I/O. Every handler returns the
contracts-v1 envelope ``{ok, data, error_code, correlation_id}`` so the fake can
later be replaced by the hosted HTTP client without changing the tool surface.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

try:  # Imported as part of a plugin package.
    from .schemas import OP_ENUMS, TOOL_SCHEMAS
except ImportError:  # Imported from a checkout with the plugin root on sys.path.
    from schemas import OP_ENUMS, TOOL_SCHEMAS

try:  # Imported as part of a plugin package.
    from .agent_policy import (
        DEFAULT_POLICY as _AGENT_DEFAULT_POLICY,
        check_budget as _check_budget,
        check_mutation as _check_mutation,
    )
except ImportError:  # Imported from a checkout with the plugin root on sys.path.
    from agent_policy import (
        DEFAULT_POLICY as _AGENT_DEFAULT_POLICY,
        check_budget as _check_budget,
        check_mutation as _check_mutation,
    )

try:  # Imported as part of a plugin package.
    from .npc_lines import host_payload as _npc_host_payload
except ImportError:  # Imported from a checkout with the plugin root on sys.path.
    from npc_lines import host_payload as _npc_host_payload

ENVELOPE_KEYS = ("ok", "data", "error_code", "correlation_id")

DEFAULT_POLICY: dict[str, Any] = dict(_AGENT_DEFAULT_POLICY.as_dict())

MUTATING_OPS: dict[str, set[str]] = {
    "hermagotchi_status": {"pair"},
    "hermagotchi_pet": {"adopt", "rename", "set_mode", "care"},
    "hermagotchi_goals": {"set", "clear"},
    "hermagotchi_challenge": {"invite", "respond", "submit_tactics"},
    "hermagotchi_battle": {"practice", "claim"},
    "hermagotchi_shop": {"buy", "equip"},
    "hermagotchi_social": {"send", "block", "report", "taunt"},
    "hermagotchi_meta": {"claim_bounty"},
}

USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ23456789"

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


def _future_iso(seconds: int) -> str:
    return (
        (datetime.now(timezone.utc) + timedelta(seconds=seconds))
        .isoformat()
        .replace("+00:00", "Z")
    )


def _normalise_user_code(value: Any) -> str:
    return "".join(str(value or "").upper().replace("-", " ").split())


def _format_user_code(value: str) -> str:
    return f"{value[:4]}-{value[4:]}" if len(value) == 8 else value


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
        self.auth_session: dict[str, Any] | None = None
        self.pending_pairing: dict[str, Any] | None = None
        self.auth_devices: list[dict[str, Any]] = []
        self.used_user_codes: set[str] = set()
        self.expired_user_codes: set[str] = set()
        self.chat_usage: dict[str, int] = {"lobby": 0, "dm": 0}
        self.chat_usage_day = self._today()

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

        mutating = self._is_mutating(tool, op, args)
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

        if mutating:
            policy_code = _check_mutation(
                self.policy, self._policy_action(tool, op, args)
            )
            if policy_code != "ok":
                return _error(
                    self._map_policy_error(tool, op, policy_code),
                    correlation_id,
                )

        result = handler(args, correlation_id)
        if mutating and idem_key is not None and result["ok"]:
            self._idempotency[(tool, idem_key)] = dict(result)
        return result

    def _is_mutating(self, tool: str, op: str, args: dict[str, Any]) -> bool:
        if op not in MUTATING_OPS[tool]:
            return False
        if tool == "hermagotchi_status" and op == "pair":
            return bool(args.get("user_code") or args.get("revoke_device_id"))
        return True

    def _policy_action(self, tool: str, op: str, args: dict[str, Any]) -> str:
        """Map a tool op to the stable action name used by the policy gate."""

        prefix = tool[len("hermagotchi_") :] if tool.startswith("hermagotchi_") else tool
        action = f"{prefix}.{op}"
        if tool == "hermagotchi_status" and op == "pair":
            # Account pairing is a human/network-only mutation; it must not
            # require agent autonomy. ``social.block`` is the stable policy
            # action that already enforces exactly that network-only gate.
            return "social.block"
        if tool == "hermagotchi_pet":
            return f"local.{action}"
        if tool == "hermagotchi_goals" and op in {"set", "clear"}:
            chosen_by = str(args.get("chosen_by") or self.policy.get("mode", "human"))
            chosen_by = "co-op" if chosen_by == "coop" else chosen_by.lower()
            actor = "agent" if chosen_by == "agent" else "human"
            return f"goals.{op}.{actor}"
        if tool == "hermagotchi_challenge" and op == "invite":
            if args.get("mode") == "ranked":
                return "challenge.invite.ranked"
        if tool == "hermagotchi_battle" and op == "practice":
            if args.get("mode") == "ranked":
                return "battle.ranked"
        return action

    def _map_policy_error(self, tool: str, op: str, code: str) -> str:
        """Map generic policy codes onto the chat surface for taunts."""

        if tool == "hermagotchi_social" and op == "taunt":
            if code == "chat_disabled":
                return "chat.disabled"
            if code == "budget_exhausted":
                return "chat.daily_cap"
        return code

    def _today(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _chat_used(self, kind: str) -> int:
        if self.chat_usage_day != self._today():
            self.chat_usage = {"lobby": 0, "dm": 0}
            self.chat_usage_day = self._today()
        return int(self.chat_usage.get(kind, 0))

    def _chat_record(self, kind: str) -> None:
        self._chat_used(kind)
        self.chat_usage[kind] = int(self.chat_usage.get(kind, 0)) + 1

    def _chat_budget_error(
        self, kind: str, cid: str, code: str = "budget_exhausted"
    ) -> dict[str, Any] | None:
        if _check_budget(self.policy, kind, self._chat_used(kind)) != "ok":
            return _error(code, cid)
        return None

    def _self_account_id(self) -> str:
        if self.auth_session is not None:
            return str(self.auth_session.get("account_id") or "self")
        if self.pet is not None:
            return str(self.pet.get("pet_id") or "self")
        return "self"

    def _resolve_target_id(self, target: Any) -> str | None:
        if not isinstance(target, str):
            return None
        value = target.strip()
        if not value or len(value) > 64:
            return None
        if self.pet is not None and value in {
            self.pet.get("pet_id"),
            self.pet.get("name"),
        }:
            return str(self.pet.get("pet_id") or value)
        return value

    def _dm_channel_id(self, target_id: str) -> str:
        ids = sorted({self._self_account_id(), target_id})
        return "dm:" + ":".join(ids)

    def _handlers(self) -> dict[tuple[str, str], Callable[[dict[str, Any], str], dict[str, Any]]]:
        return {
            ("hermagotchi_status", "me"): self._status_me,
            ("hermagotchi_status", "pet"): self._status_pet,
            ("hermagotchi_status", "wallet"): self._status_wallet,
            ("hermagotchi_status", "goal"): self._status_goal,
            ("hermagotchi_status", "inbox"): self._status_inbox,
            ("hermagotchi_status", "health"): self._status_health,
            ("hermagotchi_status", "pair"): self._status_pair,
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
            ("hermagotchi_social", "inbox"): self._social_inbox,
            ("hermagotchi_social", "taunt"): self._social_taunt,
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

    def _status_pair(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        revoke_id = args.get("revoke_device_id")
        if revoke_id is not None:
            return self._pair_revoke(revoke_id, cid)
        user_code = args.get("user_code")
        if user_code is not None:
            return self._pair_approve(user_code, cid)
        if self.auth_session is not None:
            return _ok(self._pair_session_view(), cid)
        return self._pair_start_or_poll(args, cid)

    def _pair_start_or_poll(
        self, args: dict[str, Any], cid: str
    ) -> dict[str, Any]:
        pending = self.pending_pairing
        if pending is not None:
            expires_at_ts = pending.get("expires_at_ts")
            if (
                expires_at_ts is not None
                and expires_at_ts < datetime.now(timezone.utc).timestamp()
            ):
                self.expired_user_codes.add(str(pending.get("user_code") or ""))
                self.pending_pairing = None
                return _error("expired_token", cid)
            if not pending.get("approved"):
                return _ok(self._pair_pending_view(pending), cid)
            return self._pair_complete(pending, cid)

        name = args.get("device_name") or "Hermes"
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 64:
            return _error("invalid_arguments", cid)
        name = name.strip()
        new_account = bool(args.get("new_account"))
        self._counter += 1
        code = "".join(
            USER_CODE_ALPHABET[(self._counter * 7 + index * 3) % len(USER_CODE_ALPHABET)]
            for index in range(8)
        )
        pending = {
            "user_code": code,
            "device_name": name,
            "new_account": new_account,
            "approved": new_account,
            "account_id": self._next_id("acct") if new_account else None,
            "expires_at": _future_iso(600),
            "expires_at_ts": datetime.now(timezone.utc).timestamp() + 600,
            "interval_s": 5,
        }
        self.pending_pairing = pending
        return _ok(self._pair_pending_view(pending), cid)

    def _pair_pending_view(self, pending: dict[str, Any]) -> dict[str, Any]:
        return {
            "user_code": _format_user_code(pending["user_code"]),
            "device_name": pending["device_name"],
            "paired": False,
            "account_id": None,
            "devices": [],
            "new_account": bool(pending["new_account"]),
            "interval_s": 5,
            "expires_at": pending["expires_at"],
        }

    def _pair_complete(
        self, pending: dict[str, Any], cid: str
    ) -> dict[str, Any]:
        account_id = pending.get("account_id") or self._next_id("acct")
        device_id = self._next_id("dev")
        now = _now()
        device = {
            "device_id": device_id,
            "device_name": pending["device_name"],
            "created_at": now,
            "last_seen_at": now,
            "current": True,
            "revoked": False,
        }
        self.auth_devices.append(device)
        self.auth_session = {
            "account_id": account_id,
            "device_id": device_id,
            "device_name": pending["device_name"],
        }
        self.used_user_codes.add(str(pending.get("user_code") or ""))
        self.pending_pairing = None
        return _ok(self._pair_session_view(), cid)

    def _pair_session_view(self) -> dict[str, Any]:
        assert self.auth_session is not None
        device_id = self.auth_session["device_id"]
        devices = [
            {**device, "current": device["device_id"] == device_id}
            for device in self.auth_devices
        ]
        return {
            "paired": True,
            "account_id": self.auth_session["account_id"],
            "device_name": self.auth_session["device_name"],
            "devices": devices,
        }

    def _pair_approve(self, user_code: Any, cid: str) -> dict[str, Any]:
        if self.auth_session is None:
            return _error("unauthorized", cid)
        code = _normalise_user_code(user_code)
        if not code:
            return _error("invalid_user_code", cid)
        pending = self.pending_pairing
        if pending is None or pending.get("user_code") != code:
            if code in self.used_user_codes:
                return _error("already_used", cid)
            if code in self.expired_user_codes:
                return _error("expired_token", cid)
            return _error("invalid_user_code", cid)
        expires_at_ts = pending.get("expires_at_ts")
        if (
            expires_at_ts is not None
            and expires_at_ts < datetime.now(timezone.utc).timestamp()
        ):
            self.expired_user_codes.add(code)
            self.pending_pairing = None
            return _error("expired_token", cid)
        if pending.get("approved"):
            self.used_user_codes.add(code)
            return _error("already_used", cid)
        pending["approved"] = True
        pending["account_id"] = self.auth_session["account_id"]
        return _ok(
            {"approved": True, "device_name": pending["device_name"]}, cid
        )

    def _pair_revoke(self, device_id: Any, cid: str) -> dict[str, Any]:
        if self.auth_session is None:
            return _error("unauthorized", cid)
        if not isinstance(device_id, str) or not device_id.strip():
            return _error("invalid_arguments", cid)
        value = device_id.strip()
        device = next(
            (row for row in self.auth_devices if row["device_id"] == value), None
        )
        if device is None:
            return _error("not_found", cid)
        device["revoked"] = True
        current = self.auth_session.get("device_id") == value
        if current:
            self.auth_session = None
        return _ok(
            {
                "revoked": True,
                "device_id": value,
                "revoked_current": current,
                "paired": self.auth_session is not None,
                "account_id": (
                    self.auth_session["account_id"]
                    if self.auth_session is not None
                    else None
                ),
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
        # Lazy import keeps the tool surface import-safe when the hosted client
        # extras are absent and avoids any network/asset work during planning.
        try:
            from .game_client.goals import make_goal, validate_goal
        except ImportError:
            from game_client.goals import make_goal, validate_goal

        target_type = args.get("target_type") or args.get("type")
        target_id = args.get("target_id")
        chosen_by = args.get("chosen_by") or self.policy.get("mode", "human")
        expires_at = args.get("expires_at")
        if expires_at is None:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(hours=24)
            ).isoformat(timespec="seconds").replace("+00:00", "Z")

        goal = make_goal(
            target_type,
            target_id if isinstance(target_id, str) else "",
            chosen_by=str(chosen_by),
            spending_limit_bits=args.get("spending_limit_bits", 0),
            max_battles=args.get("max_battles", 0),
            expires_at=expires_at,
        )
        if validate_goal(goal) != "ok":
            return _error("invalid_arguments", cid)
        self.goal = goal.to_dict()
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
        host_ctx = "practice.win" if match.get("winner") == "self" else "practice.loss"
        data = {"match": match}
        data.update(_npc_host_payload(host_ctx, seed=match_id))
        tip = _npc_host_payload("practice.tip", seed=f"{match_id}:tip")
        if tip:
            data["npc_tip"] = tip["npc_host"]
        return _ok(data, cid)

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
        data = {"catalog_version": "fake-1", "items": list(CATALOG)}
        data.update(_npc_host_payload("shop.greet", seed="shop.catalog"))
        return _ok(data, cid)

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
        data = {"item": self.inventory[item_id], "balance": self.wallet_bits}
        data.update(_npc_host_payload("shop.purchase", seed=str(item_id)))
        return _ok(data, cid)

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
        data = {"messages": []}
        data.update(_npc_host_payload("lobby.welcome", seed="social.read"))
        return _ok(data, cid)

    def _social_send(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        body = args.get("body")
        if not isinstance(body, str) or not body.strip() or len(body) > 500:
            return _error("invalid_arguments", cid)

        target = args.get("target")
        target_id: str | None = None
        if target is not None:
            target_id = self._resolve_target_id(target)
            if target_id is None:
                return _error("invalid_arguments", cid)
            channel_id = self._dm_channel_id(target_id)
            kind = "dm"
        else:
            channel_id = args.get("channel_id")
            if args.get("lobby") is True:
                channel_id = "lobby"
            if not isinstance(channel_id, str) or not channel_id.strip():
                return _error("invalid_arguments", cid)
            channel_id = channel_id.strip()
            kind = "lobby"

        budget_error = self._chat_budget_error(kind, cid)
        if budget_error is not None:
            return budget_error
        self._chat_record(kind)

        message = {
            "message_id": self._next_id("msg"),
            "channel_id": channel_id,
            "body": body,
            "created_at": _now(),
        }
        if target_id is not None:
            message["target_id"] = target_id
            message["dm"] = True
        return _ok({"message": message}, cid)

    def _social_inbox(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        # Offline read stub matching the hosted inbox shape.
        return _ok(
            {
                "unread": [],
                "mentions": [],
                "count": 0,
            },
            cid,
        )

    def _social_taunt(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        match_id = args.get("match_id")
        body = args.get("body")
        phase = args.get("phase")
        if (
            not isinstance(match_id, str)
            or not match_id.strip()
            or not isinstance(body, str)
            or not body.strip()
            or len(body) > 500
            or phase not in ("pre", "post")
        ):
            return _error("invalid_arguments", cid)

        budget_error = self._chat_budget_error("lobby", cid, "chat.daily_cap")
        if budget_error is not None:
            return budget_error
        self._chat_record("lobby")

        match_id = match_id.strip()
        message = {
            "message_id": self._next_id("msg"),
            "channel_id": f"match:{match_id}",
            "match_id": match_id,
            "body": body,
            "phase": phase,
            "created_at": _now(),
        }
        match_context = {
            "match_id": match_id,
            "phase": phase,
            "status": "stub",
            "opponent": None,
        }
        return _ok({"message": message, "match_context": match_context}, cid)

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
        data = {
            "report": {
                "report_id": self._next_id("report"),
                "target_id": target_id,
                "reason": reason,
                "status": "received",
            }
        }
        data.update(_npc_host_payload("lobby.moderation", seed=str(target_id)))
        return _ok(data, cid)

    # -- meta -------------------------------------------------------------
    def _meta_leaderboard(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        data = {
            "season_id": args.get("season_id", "season-1"),
            "entries": [],
        }
        data.update(_npc_host_payload("leaderboard.announce", seed=str(data["season_id"])))
        return _ok(data, cid)

    def _meta_bounties(self, args: dict[str, Any], cid: str) -> dict[str, Any]:
        blocked = self._require_network(cid)
        if blocked:
            return blocked
        data = {
            "bounties": [
                {**bounty, "claimed": bounty["bounty_id"] in self.claimed_bounties}
                for bounty in BOUNTIES
            ]
        }
        data.update(_npc_host_payload("bounty.announce", seed="meta.bounties"))
        return _ok(data, cid)

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
