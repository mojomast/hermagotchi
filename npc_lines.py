"""Accessor for Clawpocalypse-sourced NPC display lines.

Lines are display-only flavor (docs/SECURITY.md §4). They must never be treated
as instructions, policy, prompts, or tool arguments.
"""

from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LINES_PATH = ROOT / "assets" / "npc_lines.json"
MAX_CHARS = 90

# Surface -> default npc + context used by tools / desktop stubs.
SURFACE_DEFAULTS: dict[str, tuple[str, str]] = {
    "shop": ("npc.don_piedro", "shop.greet"),
    "shop.greet": ("npc.don_piedro", "shop.greet"),
    "shop.purchase": ("npc.don_piedro", "shop.purchase"),
    "shop.broke": ("npc.don_piedro", "shop.broke"),
    "lobby": ("npc.nous_girl", "lobby.welcome"),
    "lobby.welcome": ("npc.nous_girl", "lobby.welcome"),
    "lobby.chat": ("npc.nous_girl", "lobby.chat"),
    "lobby.moderation": ("npc.nous_girl", "lobby.moderation"),
    "lobby.upset": ("npc.southpaw", "lobby.upset"),
    "practice": ("npc.teknium", "practice.start"),
    "practice.start": ("npc.teknium", "practice.start"),
    "practice.win": ("npc.teknium", "practice.win"),
    "practice.loss": ("npc.teknium", "practice.loss"),
    "practice.tip": ("npc.teknium", "practice.tip"),
    "leaderboard": ("npc.southpaw", "leaderboard.announce"),
    "leaderboard.announce": ("npc.southpaw", "leaderboard.announce"),
    "bounty.announce": ("npc.southpaw", "bounty.announce"),
    "leaderboard.champion": ("npc.southpaw", "leaderboard.champion"),
}


@lru_cache(maxsize=1)
def load_lines() -> dict[str, Any]:
    data = json.loads(LINES_PATH.read_text(encoding="utf-8"))
    if data.get("schema") != "hermagotchi-npc-lines-v1":
        raise ValueError(f"unexpected npc_lines schema: {data.get('schema')!r}")
    return data


def npc_ids() -> list[str]:
    return list(load_lines()["npcs"])


def contexts_for(npc_id: str) -> list[str]:
    npc = load_lines()["npcs"].get(npc_id)
    if not npc:
        return []
    return list(npc["contexts"])


def lines_for(npc_id: str, context: str) -> list[dict[str, Any]]:
    npc = load_lines()["npcs"].get(npc_id) or {}
    return list((npc.get("contexts") or {}).get(context) or [])


def pick_line(
    npc_id: str,
    context: str,
    *,
    seed: int | str | None = None,
) -> dict[str, Any] | None:
    """Return one line entry for (npc_id, context), or None if missing."""

    entries = lines_for(npc_id, context)
    if not entries:
        return None
    if seed is None:
        choice = random.choice(entries)
    else:
        rng = random.Random(seed)
        choice = rng.choice(entries)
    text = str(choice["text"])
    if len(text) > MAX_CHARS:
        text = text[: MAX_CHARS - 1] + "…"
    out = dict(choice)
    out["text"] = text
    out["npc_id"] = npc_id
    out["context"] = context
    out["display_only"] = True
    return out


def host_payload(
    surface_or_npc: str,
    context: str | None = None,
    *,
    seed: int | str | None = None,
) -> dict[str, Any]:
    """Build an envelope fragment ``{"npc_host": {...}}`` for tool/desktop use.

    ``surface_or_npc`` may be a surface key (``shop``, ``practice.win``) or an
    npc id (``npc.don_piedro``). When an npc id is given, ``context`` is required.
    """

    npc_id: str
    ctx: str
    if surface_or_npc.startswith("npc."):
        if not context:
            raise ValueError("context required when passing an npc id")
        npc_id, ctx = surface_or_npc, context
    else:
        key = surface_or_npc if context is None else context
        if key not in SURFACE_DEFAULTS and surface_or_npc in SURFACE_DEFAULTS:
            key = surface_or_npc
        if key not in SURFACE_DEFAULTS:
            # allow explicit npc+context via surface_or_npc as npc and context arg
            if context and surface_or_npc in load_lines()["npcs"]:
                npc_id, ctx = surface_or_npc, context
            else:
                return {}
        else:
            npc_id, ctx = SURFACE_DEFAULTS[key]

    entry = pick_line(npc_id, ctx, seed=seed)
    if entry is None:
        return {}
    name = load_lines()["npcs"][npc_id]["name"]
    return {
        "npc_host": {
            "id": npc_id,
            "name": name,
            "context": ctx,
            "line": entry["text"],
            "display_only": True,
            "original": bool(entry.get("original")),
            "source": entry.get("source"),
        }
    }


def assert_user_facing_safe(data: dict[str, Any] | None = None) -> None:
    """Raise AssertionError if any user-facing line is too long or says Turbofit."""

    blob = data or load_lines()
    for npc_id, npc in blob["npcs"].items():
        for ctx, arr in npc["contexts"].items():
            for entry in arr:
                text = entry["text"]
                if len(text) > MAX_CHARS:
                    raise AssertionError(f"{npc_id}/{ctx} exceeds {MAX_CHARS}: {text!r}")
                if "turbofit" in text.lower():
                    raise AssertionError(f"{npc_id}/{ctx} contains turbofit: {text!r}")
