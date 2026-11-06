#!/usr/bin/env python3
"""Live Hermagotchi API smoke helpers.

Reads HERMAGOTCHI_API_BASE_URL (default https://api.hermagotchi.rizz.click/v1)
and HERMES_PLUGIN_DATA_DIR (session store root). Never prints tokens, device
codes, refresh tokens, or session file contents — only ids, statuses, and paths.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_client.auth import PairingClient, SessionStore  # noqa: E402
from game_client.client import GameClient  # noqa: E402
from game_client.errors import GameClientError  # noqa: E402

DEFAULT_BASE = "https://api.hermagotchi.rizz.click/v1"

TACTIC_A = {
    "ruleset_version": "battle-1",
    "stance": "aggressive",
    "actions": [
        {"when": {"special_ready": True}, "move": "glitch_pulse"},
        {"when": {"always": True}, "move": "basic_attack"},
    ],
}
TACTIC_B = {
    "ruleset_version": "battle-1",
    "stance": "defensive",
    "actions": [
        {"when": {"self_hp_lte_pct": 35}, "move": "guard"},
        {"when": {"always": True}, "move": "basic_attack"},
    ],
}


def _base() -> str:
    return os.environ.get("HERMAGOTCHI_API_BASE_URL", DEFAULT_BASE).strip().rstrip("/")


def _report(path: Path | None, payload: dict[str, Any]) -> None:
    safe = json.dumps(payload, indent=2, sort_keys=True)
    print(safe)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(safe + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def _client(store: SessionStore) -> tuple[PairingClient, GameClient]:
    base = _base()
    pair = PairingClient(base_url=base, store=store, environ=os.environ)
    game = GameClient(
        base_url=base,
        auth_token=store.access_token,
        token_provider=lambda: store.access_token,
    )
    return pair, game


def _auth_headers(store: SessionStore) -> dict[str, str]:
    token = store.access_token
    if not token:
        raise SystemExit("no access token in session store")
    return {"Authorization": f"Bearer {token}"}


def cmd_bootstrap(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(data_dir, 0o700)
    os.environ["HERMES_PLUGIN_DATA_DIR"] = str(data_dir)
    store = SessionStore(environ=os.environ)
    pair, _game = _client(store)

    out: dict[str, Any] = {
        "ok": True,
        "checks": {},
        "session_path": str(store.path),
        "api_base": _base(),
        "species": args.species,
        "handle": args.handle,
    }

    try:
        started = pair.start(
            args.device_name,
            new_account=True,
            public_handle=args.handle,
        )
        # device_code is secret — do not put in report
        device_code = started["device_code"]
        tokens = pair.poll_token(device_code)
        out["account_id"] = tokens.get("account_id") or store.account_id
        out["device_id"] = tokens.get("device_id") or store.device_id
        out["checks"]["pair_new_account"] = "pass"
    except GameClientError as exc:
        out["ok"] = False
        out["checks"]["pair_new_account"] = f"fail:{exc.code}"
        _report(Path(args.report) if args.report else None, out)
        return 1

    # adopt
    try:
        import httpx

        h = _auth_headers(store)
        r = httpx.post(
            f"{_base()}/pets",
            headers=h,
            json={"species": args.species, "name": args.pet_name, "mode": "human"},
            timeout=30,
        )
        if r.status_code not in (200, 201):
            raise GameClientError(
                r.json().get("code", "http"),
                r.json().get("message", r.text[:120]),
                status_code=r.status_code,
            )
        pet = r.json()
        out["pet_id"] = pet["id"]
        out["pet_species"] = pet["species"]
        out["checks"]["adopt"] = "pass"
    except GameClientError as exc:
        out["ok"] = False
        out["checks"]["adopt"] = f"fail:{exc.code}"
        _report(Path(args.report) if args.report else None, out)
        return 1

    import httpx

    h = _auth_headers(store)
    # care
    care_ok = []
    for action in ("feed", "play", "rest"):
        rr = httpx.post(
            f"{_base()}/pets/{out['pet_id']}/care",
            headers={**h, "Idempotency-Key": str(uuid.uuid4())},
            json={"action": action},
            timeout=30,
        )
        care_ok.append(rr.status_code in (200, 201))
        if rr.status_code not in (200, 201):
            out["checks"][f"care_{action}"] = f"fail:{rr.status_code}:{rr.json().get('code') if rr.content else ''}"
        else:
            out["checks"][f"care_{action}"] = "pass"
    out["checks"]["care"] = "pass" if all(care_ok) else "fail"

    # /me
    me = httpx.get(f"{_base()}/me", headers=h, timeout=30)
    out["checks"]["me"] = "pass" if me.status_code == 200 else f"fail:{me.status_code}"
    if me.status_code == 200:
        body = me.json()
        out["me_pet_id"] = body.get("pet_id")

    # practice for bits (before shop)
    prac = httpx.post(
        f"{_base()}/practice",
        headers=h,
        json={"pet_id": out["pet_id"], "tactics": TACTIC_A},
        timeout=60,
    )
    out["checks"]["practice"] = (
        "pass" if prac.status_code in (200, 201) else f"fail:{prac.status_code}:{prac.json().get('code') if prac.content else ''}"
    )
    if prac.status_code in (200, 201):
        pdata = prac.json()
        out["practice_match_id"] = pdata.get("match_id") or (pdata.get("match") or {}).get("id")
        out["practice_winner"] = pdata.get("winner") or (pdata.get("match") or {}).get("winner")
        replay = pdata.get("replay") or {}
        turns = replay.get("turns") or replay.get("rounds") or []
        out["practice_turn_count"] = len(turns) if isinstance(turns, list) else None
        # notable lines
        notes = []
        for t in (turns if isinstance(turns, list) else [])[:8]:
            if isinstance(t, dict):
                notes.append(
                    {
                        "round": t.get("round") or t.get("n"),
                        "move_a": t.get("move_a") or (t.get("a") or {}).get("move"),
                        "move_b": t.get("move_b") or (t.get("b") or {}).get("move"),
                        "eff": t.get("effectiveness") or t.get("effectiveness_a"),
                    }
                )
        out["practice_notes"] = notes

    # catalog + buy cheap head item
    cat = httpx.get(f"{_base()}/catalog", headers=h, timeout=30)
    out["checks"]["catalog"] = "pass" if cat.status_code == 200 else f"fail:{cat.status_code}"
    item_id = None
    if cat.status_code == 200:
        items = cat.json().get("items") or []
        out["catalog_count"] = len(items)
        cheap = sorted(
            [i for i in items if i.get("slot") == "head" and int(i.get("price_bits") or 0) > 0],
            key=lambda i: int(i.get("price_bits") or 0),
        )
        if cheap:
            item_id = cheap[0]["id"]
            out["buy_item_id"] = item_id
            out["buy_price"] = cheap[0].get("price_bits")

    wallet = httpx.get(f"{_base()}/wallet", headers=h, timeout=30)
    if wallet.status_code == 200:
        out["bits"] = wallet.json().get("balance")
    out["checks"]["wallet"] = "pass" if wallet.status_code == 200 else f"fail:{wallet.status_code}"

    if item_id:
        buy = httpx.post(
            f"{_base()}/shop/purchases",
            headers={**h, "Idempotency-Key": str(uuid.uuid4())},
            json={"item_id": item_id},
            timeout=30,
        )
        out["checks"]["buy"] = (
            "pass" if buy.status_code in (200, 201) else f"fail:{buy.status_code}:{buy.json().get('code') if buy.content else ''}"
        )
        if buy.status_code in (200, 201):
            eq = httpx.post(
                f"{_base()}/pets/{out['pet_id']}/equip",
                headers={**h, "Idempotency-Key": str(uuid.uuid4())},
                json={"item_id": item_id, "slot": "head"},
                timeout=30,
            )
            out["checks"]["equip"] = (
                "pass" if eq.status_code in (200, 201) else f"fail:{eq.status_code}:{eq.json().get('code') if eq.content else ''}"
            )
    else:
        out["checks"]["buy"] = "skip:no_item"
        out["checks"]["equip"] = "skip"

    # leaderboard
    lb = httpx.get(f"{_base()}/leaderboard", headers=h, timeout=30)
    out["checks"]["leaderboard"] = "pass" if lb.status_code == 200 else f"fail:{lb.status_code}"
    if lb.status_code == 200:
        rows = lb.json().get("rows") or lb.json().get("entries") or []
        out["leaderboard_rows"] = len(rows) if isinstance(rows, list) else None

    # chat (may be disabled)
    chat = httpx.get(f"{_base()}/chat/messages", headers=h, timeout=30)
    if chat.status_code == 200:
        out["checks"]["chat"] = "pass"
        out["chat_count"] = len(chat.json().get("messages") or chat.json().get("items") or [])
    elif chat.status_code in (403, 404, 501, 503):
        out["checks"]["chat"] = f"skip:{chat.status_code}:{chat.json().get('code') if chat.content else ''}"
    else:
        out["checks"]["chat"] = f"fail:{chat.status_code}"

    mode = oct(store.path.stat().st_mode & 0o777)
    out["session_mode"] = mode
    out["checks"]["session_0600"] = "pass" if (store.path.stat().st_mode & 0o777) == 0o600 else f"fail:{mode}"

    _report(Path(args.report) if args.report else None, out)
    return 0 if out["ok"] and all(
        str(v).startswith("pass") or str(v).startswith("skip") for k, v in out["checks"].items()
    ) else 1


def cmd_auth_checks(args: argparse.Namespace) -> int:
    import httpx

    data_dir = Path(args.data_dir).resolve()
    os.environ["HERMES_PLUGIN_DATA_DIR"] = str(data_dir)
    store = SessionStore(environ=os.environ)
    pair, _game = _client(store)
    out: dict[str, Any] = {"ok": True, "checks": {}, "account_id": store.account_id}
    base = _base()

    # X-Account-Id only (before any refresh games)
    r = httpx.get(
        f"{base}/me",
        headers={"X-Account-Id": store.account_id or "00000000-0000-4000-8000-000000000099"},
        timeout=30,
    )
    out["checks"]["x_account_id_401"] = "pass" if r.status_code == 401 else f"fail:{r.status_code}"

    # bad pairing lockout while still authenticated
    h = _auth_headers(store)
    locked = False
    last = None
    for i in range(20):
        rr = httpx.post(
            f"{base}/auth/pair/approve",
            headers=h,
            json={"user_code": f"BADQ-COD{i}"},
            timeout=30,
        )
        last = (rr.status_code, (rr.json() or {}).get("code") if rr.content else None)
        if rr.status_code == 429 or (last[1] in {"rate_limited", "slow_down"}):
            locked = True
            break
    out["checks"]["bad_code_lockout"] = "pass" if locked else f"fail:last={last}"

    # second device pair + revoke (before refresh-reuse, which revokes the device)
    try:
        started = pair.start("live-smoke-extra-device", new_account=False)
        user_code = started["user_code"]
        device_code = started["device_code"]
        pair.approve(user_code)
        extra_dir = data_dir / "extra-device"
        extra_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(extra_dir, 0o700)
        env2 = dict(os.environ)
        env2["HERMES_PLUGIN_DATA_DIR"] = str(extra_dir)
        store2 = SessionStore(environ=env2)
        pair2 = PairingClient(base_url=base, store=store2, environ=env2)
        pair2.poll_token(device_code)
        devices = pair.list_devices()
        rows = devices.get("devices") or []
        out["device_count_after_pair"] = len(rows)
        extra_id = store2.device_id
        out["extra_device_id"] = extra_id
        out["checks"]["extra_device_pair"] = "pass" if extra_id else "fail"
        if extra_id:
            rr = httpx.post(
                f"{base}/auth/devices/{extra_id}/revoke",
                headers=_auth_headers(store),
                timeout=30,
            )
            out["checks"]["revoke_extra_device"] = (
                "pass" if rr.status_code in (200, 204) else f"fail:{rr.status_code}:{(rr.json() or {}).get('code') if rr.content else ''}"
            )
        devices2 = pair.list_devices()
        rows2 = devices2.get("devices") or []
        out["device_count_after_revoke"] = len(rows2)
        active = [d for d in rows2 if not d.get("revoked") and not d.get("revoked_at")]
        out["active_devices_after_revoke"] = len(active)
    except GameClientError as exc:
        out["checks"]["extra_device_pair"] = f"fail:{exc.code}"
        out["ok"] = False
    except Exception as exc:  # noqa: BLE001
        out["checks"]["extra_device_pair"] = f"fail:{type(exc).__name__}:{exc}"
        out["ok"] = False

    # refresh rotation LAST — reusing the old refresh token revokes the device by design
    try:
        old_access = store.access_token
        old_refresh = store.refresh_token
        pair.refresh()
        new_access = store.access_token
        new_refresh = store.refresh_token
        rotated = bool(
            new_access
            and new_access != old_access
            and new_refresh
            and new_refresh != old_refresh
        )
        out["checks"]["refresh_rotation"] = "pass" if rotated else "fail:tokens_unchanged"
        r = httpx.post(
            f"{base}/auth/refresh",
            json={"refresh_token": old_refresh},
            timeout=30,
        )
        out["checks"]["old_refresh_rejected"] = (
            "pass" if r.status_code == 401 else f"fail:{r.status_code}"
        )
        out["checks"]["old_refresh_note"] = (
            "pass:reuse_revokes_device_by_design"
        )
    except GameClientError as exc:
        out["checks"]["refresh_rotation"] = f"fail:{exc.code}"
        out["ok"] = False

    _report(Path(args.report) if args.report else None, out)
    fails = [k for k, v in out["checks"].items() if str(v).startswith("fail")]
    return 0 if not fails else 1



def cmd_challenge(args: argparse.Namespace) -> int:
    import httpx

    data_dir = Path(args.data_dir).resolve()
    os.environ["HERMES_PLUGIN_DATA_DIR"] = str(data_dir)
    store = SessionStore(environ=os.environ)
    h = _auth_headers(store)
    body = {"defender_id": args.defender, "mode": args.mode}
    r = httpx.post(
        f"{_base()}/challenges",
        headers={**h, "Idempotency-Key": str(uuid.uuid4())},
        json=body,
        timeout=30,
    )
    out = {
        "status": r.status_code,
        "challenge_id": (r.json() or {}).get("id") if r.content else None,
        "challenge_status": (r.json() or {}).get("status") if r.content else None,
        "code": (r.json() or {}).get("code") if r.content and r.status_code >= 400 else None,
        "account_id": store.account_id,
    }
    _report(Path(args.report) if args.report else None, out)
    return 0 if r.status_code in (200, 201) else 1


def cmd_accept_and_tactics(args: argparse.Namespace) -> int:
    import httpx

    data_dir = Path(args.data_dir).resolve()
    os.environ["HERMES_PLUGIN_DATA_DIR"] = str(data_dir)
    store = SessionStore(environ=os.environ)
    h = _auth_headers(store)
    challenge_id = args.challenge_id
    if not challenge_id:
        inbox = httpx.get(f"{_base()}/challenges/inbox", headers=h, timeout=30)
        items = []
        if inbox.status_code == 200:
            data = inbox.json()
            items = data.get("challenges") or data.get("incoming") or data.get("items") or []
        pending = [c for c in items if c.get("status") == "pending"]
        if not pending:
            _report(Path(args.report) if args.report else None, {"ok": False, "error": "no_pending"})
            return 1
        challenge_id = pending[0]["id"]

    acc = httpx.post(
        f"{_base()}/challenges/{challenge_id}/respond",
        headers=h,
        json={"action": "accept"},
        timeout=30,
    )
    match = None
    if acc.status_code == 200:
        match = (acc.json() or {}).get("match")
    match_id = (match or {}).get("id")
    card = TACTIC_B if args.card == "b" else TACTIC_A
    tactics_status = None
    match_after = None
    if match_id:
        t = httpx.post(
            f"{_base()}/matches/{match_id}/tactics",
            headers=h,
            json={"card": card},
            timeout=60,
        )
        tactics_status = t.status_code
        if t.status_code in (200, 201):
            match_after = t.json().get("match") or t.json()
    out = {
        "ok": acc.status_code == 200,
        "challenge_id": challenge_id,
        "accept_status": acc.status_code,
        "match_id": match_id,
        "tactics_status": tactics_status,
        "winner": (match_after or {}).get("winner") if isinstance(match_after, dict) else None,
        "match_status": (match_after or {}).get("status") if isinstance(match_after, dict) else None,
        "account_id": store.account_id,
    }
    _report(Path(args.report) if args.report else None, out)
    return 0 if out["ok"] else 1


def cmd_submit_tactics(args: argparse.Namespace) -> int:
    import httpx

    data_dir = Path(args.data_dir).resolve()
    os.environ["HERMES_PLUGIN_DATA_DIR"] = str(data_dir)
    store = SessionStore(environ=os.environ)
    h = _auth_headers(store)
    card = TACTIC_B if args.card == "b" else TACTIC_A
    t = httpx.post(
        f"{_base()}/matches/{args.match_id}/tactics",
        headers=h,
        json={"card": card},
        timeout=60,
    )
    body = t.json() if t.content else {}
    match = body.get("match") or body
    replay = body.get("replay") or {}
    turns = replay.get("turns") or replay.get("rounds") or []
    notes = []
    for row in (turns if isinstance(turns, list) else [])[:10]:
        if isinstance(row, dict):
            notes.append(
                {
                    "round": row.get("round") or row.get("n"),
                    "a": row.get("move_a") or (row.get("a") or {}).get("move"),
                    "b": row.get("move_b") or (row.get("b") or {}).get("move"),
                    "hp_a": row.get("hp_a") or (row.get("a") or {}).get("hp"),
                    "hp_b": row.get("hp_b") or (row.get("b") or {}).get("hp"),
                }
            )
    out = {
        "status": t.status_code,
        "match_id": args.match_id,
        "winner": match.get("winner") if isinstance(match, dict) else None,
        "match_status": match.get("status") if isinstance(match, dict) else None,
        "turn_count": len(turns) if isinstance(turns, list) else None,
        "notes": notes,
        "code": body.get("code") if t.status_code >= 400 else None,
        "account_id": store.account_id,
    }
    _report(Path(args.report) if args.report else None, out)
    return 0 if t.status_code in (200, 201) else 1


def cmd_practice(args: argparse.Namespace) -> int:
    import httpx

    data_dir = Path(args.data_dir).resolve()
    os.environ["HERMES_PLUGIN_DATA_DIR"] = str(data_dir)
    store = SessionStore(environ=os.environ)
    h = _auth_headers(store)
    pet_id = args.pet_id
    if not pet_id:
        me = httpx.get(f"{_base()}/me", headers=h, timeout=30).json()
        pet_id = me.get("pet_id")
    r = httpx.post(
        f"{_base()}/practice",
        headers=h,
        json={"pet_id": pet_id, "tactics": TACTIC_A},
        timeout=60,
    )
    body = r.json() if r.content else {}
    replay = body.get("replay") or {}
    turns = replay.get("turns") or replay.get("rounds") or []
    out = {
        "status": r.status_code,
        "match_id": body.get("match_id") or (body.get("match") or {}).get("id"),
        "winner": body.get("winner") or (body.get("match") or {}).get("winner"),
        "turn_count": len(turns) if isinstance(turns, list) else None,
        "code": body.get("code") if r.status_code >= 400 else None,
        "account_id": store.account_id,
        "pet_id": pet_id,
    }
    _report(Path(args.report) if args.report else None, out)
    return 0 if r.status_code in (200, 201) else 1


def cmd_inbox(args: argparse.Namespace) -> int:
    import httpx

    data_dir = Path(args.data_dir).resolve()
    os.environ["HERMES_PLUGIN_DATA_DIR"] = str(data_dir)
    store = SessionStore(environ=os.environ)
    h = _auth_headers(store)
    r = httpx.get(f"{_base()}/challenges/inbox", headers=h, timeout=30)
    data = r.json() if r.content else {}
    items = data.get("challenges") or data.get("incoming") or data.get("items") or []
    slim = [
        {
            "id": c.get("id"),
            "status": c.get("status"),
            "mode": c.get("mode"),
            "challenger_id": c.get("challenger_id"),
            "defender_id": c.get("defender_id"),
        }
        for c in items
        if isinstance(c, dict)
    ]
    _report(Path(args.report) if args.report else None, {"status": r.status_code, "challenges": slim, "account_id": store.account_id})
    return 0 if r.status_code == 200 else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", required=True, help="HERMES_PLUGIN_DATA_DIR for this actor")
    p.add_argument("--report", default="", help="Write JSON report (0600); still prints safe JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bootstrap")
    b.add_argument("--species", default="patchfox")
    b.add_argument("--pet-name", default="LiveBox")
    b.add_argument("--handle", default="livebox")
    b.add_argument("--device-name", default="box-live-smoke")
    b.set_defaults(func=cmd_bootstrap)

    a = sub.add_parser("auth-checks")
    a.set_defaults(func=cmd_auth_checks)

    c = sub.add_parser("challenge")
    c.add_argument("--defender", required=True)
    c.add_argument("--mode", default="casual")
    c.set_defaults(func=cmd_challenge)

    ac = sub.add_parser("accept")
    ac.add_argument("--challenge-id", default="")
    ac.add_argument("--card", choices=("a", "b"), default="b")
    ac.set_defaults(func=cmd_accept_and_tactics)

    st = sub.add_parser("tactics")
    st.add_argument("--match-id", required=True)
    st.add_argument("--card", choices=("a", "b"), default="a")
    st.set_defaults(func=cmd_submit_tactics)

    pr = sub.add_parser("practice")
    pr.add_argument("--pet-id", default="")
    pr.set_defaults(func=cmd_practice)

    ib = sub.add_parser("inbox")
    ib.set_defaults(func=cmd_inbox)

    args = p.parse_args()
    if args.report == "":
        args.report = None
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
