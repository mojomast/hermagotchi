"""Online backend for the eight Hermagotchi agent tools.

When the owner turns ``network_enabled`` on (plugin setting or the
``HERMAGOTCHI_NETWORK_ENABLED`` env switch), the tools act on the real shared
game server through the same paired device session the dashboard/Desktop pane
uses (``SessionStore`` under Hermes plugin data, mode 0600). State then lives
on the server and survives Hermes restarts. Otherwise the tools stay on the
in-memory offline practice simulation (``tools.FakeGameClient``).

Tokens are never returned, logged, or placed in tool results.
"""

from __future__ import annotations

import os
import re
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode

try:
    from .game_client import DEFAULT_API_BASE_URL, GameClientError
    from .game_client.auth import PairingClient, SessionStore
except ImportError:  # checkout with the plugin root on sys.path
    from game_client import DEFAULT_API_BASE_URL, GameClientError
    from game_client.auth import PairingClient, SessionStore

ENV_API_BASE_URL = "HERMAGOTCHI_API_BASE_URL"
ENV_NETWORK_ENABLED = "HERMAGOTCHI_NETWORK_ENABLED"
ENV_AGENT_CHAT_ENABLED = "HERMAGOTCHI_AGENT_CHAT_ENABLED"

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.:~-]{1,128}$")
_TOKEN_TEXT = re.compile(r"hg[adr]_[A-Za-z0-9_-]{8,}")
_SENSITIVE = frozenset({"access_token", "refresh_token", "device_code", "authorization"})

# Settings getter installed by register(ctx); defaults to "no settings".
_settings_getter: Callable[[str, Any], Any] | None = None


def install_settings_getter(getter: Callable[[str, Any], Any] | None) -> None:
    global _settings_getter
    _settings_getter = getter


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _setting(key: str, env: str, environ: Mapping[str, str] | None = None) -> bool:
    if _settings_getter is not None:
        try:
            value = _settings_getter(key, None)
        except Exception:  # settings unavailable -> fall through to env
            value = None
        if value is not None:
            return _truthy(value)
    source = os.environ if environ is None else environ
    return _truthy(source.get(env, ""))


def network_enabled(environ: Mapping[str, str] | None = None) -> bool:
    return _setting("network_enabled", ENV_NETWORK_ENABLED, environ)


def agent_chat_enabled(environ: Mapping[str, str] | None = None) -> bool:
    return _setting("agent_chat_enabled", ENV_AGENT_CHAT_ENABLED, environ)


ENV_AGENT_AUTONOMY_ENABLED = "HERMAGOTCHI_AGENT_AUTONOMY_ENABLED"


def agent_autonomy_enabled(environ: Mapping[str, str] | None = None) -> bool:
    return _setting("agent_autonomy_enabled", ENV_AGENT_AUTONOMY_ENABLED, environ)


def api_base_url(environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    return str(source.get(ENV_API_BASE_URL) or DEFAULT_API_BASE_URL).strip()


def scrub(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            k: scrub(v) for k, v in value.items() if str(k).lower() not in _SENSITIVE
        }
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return _TOKEN_TEXT.sub("[redacted]", value)
    return value


class OnlineError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _seg(value: Any) -> str:
    text = str(value or "").strip()
    if not _SAFE_SEGMENT.match(text):
        raise OnlineError("invalid_arguments")
    return quote(text, safe="")


class OnlineTransport:
    """Authorized JSON calls against the game API with the pane's session."""

    def __init__(self, pair_client: PairingClient) -> None:
        self.pair = pair_client

    @classmethod
    def from_environment(cls) -> "OnlineTransport":
        return cls(PairingClient(base_url=api_base_url(), store=SessionStore()))

    @property
    def paired(self) -> bool:
        store = self.pair.store
        try:
            return bool(store.has_session)
        except Exception:
            return False

    def call(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
        public: bool = False,
    ) -> Any:
        if not public and not self.paired:
            raise OnlineError("auth_missing")
        store = self.pair.store
        session = store.load() or {}
        query = urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = self.pair._url(path) + (f"?{query}" if query else "")
        payload: dict[str, Any] | None = None
        if method.upper() != "GET":
            payload = dict(body or {})
            if idempotency_key:
                payload.setdefault("idempotency_key", idempotency_key)

        def send(token: str | None):
            headers = dict(getattr(self.pair, "_headers", {}) or {})
            if token:
                headers["Authorization"] = f"Bearer {token}"
            if idempotency_key and method.upper() != "GET":
                headers["Idempotency-Key"] = idempotency_key
            try:
                return self.pair._client.request(
                    method.upper(), url, json=payload, headers=headers
                )
            except Exception as exc:  # httpx transport errors
                raise GameClientError(
                    "network_error", "Could not reach the Hermagotchi service."
                ) from exc

        response = send(session.get("access_token") or None)
        if response.status_code == 401 and session.get("refresh_token"):
            self.pair.refresh()
            response = send(store.access_token)
        return self.pair._expect(response)


def _species(value: Any) -> Any:
    return value


def build_online_handlers(client: Any, transport: OnlineTransport) -> dict:
    """(tool, op) -> handler(args, cid) for the real game server."""

    ok, err = client._ok, client._err

    def run(fn):
        def handler(args: dict[str, Any], cid: str) -> dict[str, Any]:
            try:
                data = fn(args)
            except OnlineError as exc:
                return err(exc.code, cid)
            except GameClientError as exc:
                return err(exc.code or "unavailable", cid)
            return ok(scrub(data), cid)

        return handler

    key = lambda a: (a.get("idempotency_key") or None)  # noqa: E731
    get = lambda p, **q: transport.call("GET", p, params=q or None)  # noqa: E731

    def post(path: str, args: dict[str, Any], body: Mapping[str, Any] | None = None,
             method: str = "POST") -> Any:
        return transport.call(method, path, body=body or {}, idempotency_key=key(args))

    def pet_id() -> str:
        me = get("/me")
        pid = me.get("pet_id") if isinstance(me, Mapping) else None
        if not pid:
            raise OnlineError("no_pet")
        return _seg(pid)

    def status_me(a):
        return get("/me")

    def status_pet(a):
        return get(f"/pets/{pet_id()}")

    def status_health(a):
        data = transport.call("GET", "/healthz", public=True)
        return {"server": data, "paired": transport.paired}

    def status_pair(a):
        # Approve/revoke must stay a human pane action. The agent also reads
        # lobby messages and DMs, so a stranger could talk it into pairing
        # their device to this account (maps to social.block, no owner gate).
        if a.get("revoke_device_id") or a.get("user_code"):
            raise OnlineError("unsupported_online")
        if not transport.paired:
            raise OnlineError("pair_via_pane")
        listed = transport.pair.list_devices()
        devices = listed.get("devices") if isinstance(listed, dict) else listed
        if not isinstance(devices, list):
            devices = []
        return {"paired": True, "devices": devices}

    def pet_adopt(a):
        mode = a.get("mode") or "human"
        body = {"species": a.get("species"), "mode": "coop" if mode == "co-op" else mode}
        if a.get("name"):
            body["name"] = a["name"]
        return post("/pets", a, body)

    def unsupported(a):
        raise OnlineError("unsupported_online")

    def pet_care(a):
        return post(f"/pets/{pet_id()}/care", a, {"action": a.get("action")})

    def goals_set(a):
        body = {
            k: a[k]
            for k in ("target_type", "target_id", "chosen_by", "spending_limit_bits",
                      "max_battles", "expires_at")
            if a.get(k) is not None
        }
        return post("/goals", a, body)

    def ch_invite(a):
        return post("/challenges", a, {"opponent_id": a.get("opponent_id"),
                                        "mode": a.get("mode") or "casual"})

    def ch_respond(a):
        return post(f"/challenges/{_seg(a.get('challenge_id'))}/respond", a,
                    {"action": a.get("action")})

    def ch_tactics(a):
        return post(f"/matches/{_seg(a.get('match_id'))}/tactics", a,
                    {"tactics": a.get("tactics") or {}})

    def practice(a):
        body: dict[str, Any] = {"pet_id": pet_id()}
        if a.get("tactics"):
            body["tactics"] = a["tactics"]
        return post("/practice", a, body)

    def battle_get(a):
        return get(f"/matches/{_seg(a.get('match_id'))}")

    def battle_claim(a):
        # The server credits practice/PvP rewards when the match resolves.
        match = get(f"/matches/{_seg(a.get('match_id'))}")
        return {"auto_credited": True, "match": match}

    def shop_inventory(a):
        return {"wallet": get("/wallet"), "pet": get(f"/pets/{pet_id()}")}

    def shop_buy(a):
        return post("/shop/purchases", a, {"item_id": a.get("item_id")})

    def shop_equip(a):
        body = {"item_id": a.get("item_id")}
        if a.get("slot"):
            body["slot"] = a["slot"]
        return post(f"/pets/{pet_id()}/equip", a, body)

    def channel(a):
        return _seg(a.get("channel_id") or "lobby")

    def social_read(a):
        return get(f"/chat/channels/{channel(a)}/messages")

    def social_send(a):
        body = {"body": a.get("body"), "actor_mode": "agent"}
        if a.get("target"):
            body["target"] = a["target"]
            return post("/chat/messages", a, body)
        return post(f"/chat/channels/{channel(a)}/messages", a, body)

    def social_block(a):
        return post("/blocks", a, {"blocked_id": a.get("target_id")})

    def social_report(a):
        return post("/moderation/report", a, {
            "target_type": a.get("target_type") or "account",
            "target_id": a.get("target_id"),
            "reason": a.get("reason"),
        })

    def social_taunt(a):
        body = {"match_id": a.get("match_id"), "body": a.get("body"),
                "phase": a.get("phase") or "pre", "actor_mode": "agent"}
        if a.get("lobby") is not None:
            body["lobby"] = bool(a["lobby"])
        return post("/chat/taunt", a, body)

    def social_friends(a):
        choice = str(a.get("action") or "list").lower()
        target = a.get("target_id") or a.get("target")
        if choice == "list":
            return get("/friends")
        if choice == "add":
            return post("/friends", a, {"target": target})
        if choice in {"accept", "decline"}:
            return post(f"/friends/requests/{_seg(target)}/respond", a, {"action": choice})
        if choice == "remove":
            return transport.call("DELETE", f"/friends/{_seg(target)}",
                                  idempotency_key=key(a))
        raise OnlineError("invalid_arguments")

    def social_history(a):
        return get("/social/history", filter=a.get("filter") or "all")

    def leaderboard(a):
        return get("/leaderboard", season_id=a.get("season_id"))

    def claim_bounty(a):
        return post(f"/bounties/{_seg(a.get('bounty_id'))}/claim", a, {})

    table = {
        ("hermagotchi_status", "me"): status_me,
        ("hermagotchi_status", "pet"): status_pet,
        ("hermagotchi_status", "wallet"): lambda a: get("/wallet"),
        ("hermagotchi_status", "goal"): lambda a: get("/goals"),
        ("hermagotchi_status", "inbox"): lambda a: get("/challenges/inbox"),
        ("hermagotchi_status", "health"): status_health,
        ("hermagotchi_status", "pair"): status_pair,
        ("hermagotchi_pet", "adopt"): pet_adopt,
        ("hermagotchi_pet", "rename"): unsupported,
        ("hermagotchi_pet", "set_mode"): unsupported,
        ("hermagotchi_pet", "care"): pet_care,
        ("hermagotchi_goals", "list"): lambda a: get("/goals"),
        ("hermagotchi_goals", "set"): goals_set,
        ("hermagotchi_goals", "clear"): lambda a: post("/goals/clear", a, {}),
        ("hermagotchi_challenge", "list_opponents"): leaderboard,
        ("hermagotchi_challenge", "invite"): ch_invite,
        ("hermagotchi_challenge", "respond"): ch_respond,
        ("hermagotchi_challenge", "submit_tactics"): ch_tactics,
        ("hermagotchi_battle", "practice"): practice,
        ("hermagotchi_battle", "get"): battle_get,
        ("hermagotchi_battle", "replay"): battle_get,
        ("hermagotchi_battle", "claim"): battle_claim,
        ("hermagotchi_shop", "catalog"): lambda a: get("/catalog"),
        ("hermagotchi_shop", "inventory"): shop_inventory,
        ("hermagotchi_shop", "buy"): shop_buy,
        ("hermagotchi_shop", "equip"): shop_equip,
        ("hermagotchi_social", "read"): social_read,
        ("hermagotchi_social", "send"): social_send,
        ("hermagotchi_social", "block"): social_block,
        ("hermagotchi_social", "report"): social_report,
        ("hermagotchi_social", "inbox"): lambda a: get("/chat/inbox"),
        ("hermagotchi_social", "taunt"): social_taunt,
        ("hermagotchi_social", "friends"): social_friends,
        ("hermagotchi_social", "history"): social_history,
        ("hermagotchi_meta", "leaderboard"): leaderboard,
        ("hermagotchi_meta", "bounties"): lambda a: get("/bounties"),
        ("hermagotchi_meta", "claim_bounty"): claim_bounty,
    }
    return {k: run(v) for k, v in table.items()}
