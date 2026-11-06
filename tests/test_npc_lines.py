"""NPC quip pack: schema, length, no Turbofit, desktop sync, tool envelopes."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINES = json.loads((ROOT / "assets" / "npc_lines.json").read_text(encoding="utf-8"))
NPCS = json.loads((ROOT / "assets" / "npcs.json").read_text(encoding="utf-8"))
MAX = 90
IDS = ["npc.don_piedro", "npc.nous_girl", "npc.teknium", "npc.southpaw"]


def test_npc_lines_schema_and_npcs_ref():
    assert LINES["schema"] == "hermagotchi-npc-lines-v1"
    assert LINES["max_chars"] == MAX
    assert NPCS.get("lines_ref") == "npc_lines.json"
    assert list(LINES["npcs"]) == IDS


def test_contexts_cover_required_surfaces():
    required = {
        "npc.don_piedro": {"shop.greet", "shop.purchase", "shop.broke"},
        "npc.nous_girl": {"lobby.welcome", "lobby.chat", "lobby.moderation"},
        "npc.teknium": {"practice.start", "practice.win", "practice.loss", "practice.tip"},
        "npc.southpaw": {"leaderboard.announce", "bounty.announce", "leaderboard.champion"},
    }
    for npc_id, ctxs in required.items():
        got = set(LINES["npcs"][npc_id]["contexts"])
        assert ctxs <= got, (npc_id, ctxs - got)


def test_line_length_and_no_turbofit_in_user_facing_text():
    from npc_lines import assert_user_facing_safe

    assert_user_facing_safe(LINES)
    # also scan desktop defaults and npcs flavor_lines
    desk = (ROOT / "desktop" / "src" / "ui" / "npcLines.js").read_text(encoding="utf-8")
    assert "turbofit" not in desk.lower()
    for npc in NPCS["npcs"]:
        blob = json.dumps(npc.get("flavor_lines") or [])
        assert "turbofit" not in blob.lower()
        for line in npc.get("flavor_lines") or []:
            assert len(line) <= MAX


def test_sources_recorded_for_verbatim_and_adapted():
    for npc_id, npc in LINES["npcs"].items():
        for ctx, arr in npc["contexts"].items():
            assert arr, (npc_id, ctx)
            for entry in arr:
                assert "text" in entry and "original" in entry
                assert isinstance(entry["original"], bool)
                if entry["original"]:
                    assert entry.get("source"), (npc_id, ctx, entry["text"])
                    assert re.search(r"\.(js|mjs):\d+$", entry["source"]), entry["source"]


def test_accessor_pick_and_host_payload_deterministic():
    from npc_lines import host_payload, pick_line

    a = pick_line("npc.don_piedro", "shop.greet", seed=7)
    b = pick_line("npc.don_piedro", "shop.greet", seed=7)
    assert a == b
    assert a["display_only"] is True
    host = host_payload("shop.greet", seed=7)
    assert host["npc_host"]["id"] == "npc.don_piedro"
    assert host["npc_host"]["display_only"] is True
    assert host["npc_host"]["line"] == a["text"]


def test_desktop_defaults_subset_of_npc_lines():
    desk = (ROOT / "desktop" / "src" / "ui" / "npcLines.js").read_text(encoding="utf-8")
    texts = set()
    for npc in LINES["npcs"].values():
        for arr in npc["contexts"].values():
            for entry in arr:
                texts.add(entry["text"])
    for match in re.findall(r'"line":\s*"((?:\\.|[^"\\])*)"', desk):
        line = json.loads(f'"{match}"')
        assert line in texts, line
    assert "Southpaw" in desk
    assert "Don Piedro" in desk


def test_tool_envelopes_include_npc_host_without_schema_change():
    import tools

    client = tools.FakeGameClient(
        policy={
            "network_enabled": True,
            "agent_autonomy_enabled": True,
            "allow_cosmetic_purchases": True,
            "agent_chat_enabled": True,
        }
    )
    adopt = tools.handle_tool(
        "hermagotchi_pet",
        {"op": "adopt", "species": "byteblob", "name": "Bit", "idempotency_key": "npc-adopt-1"},
        client=client,
    )
    assert adopt["ok"], adopt

    catalog = tools.handle_tool("hermagotchi_shop", {"op": "catalog"}, client=client)
    assert catalog["ok"]
    assert catalog["data"]["npc_host"]["id"] == "npc.don_piedro"
    assert catalog["data"]["npc_host"]["display_only"] is True

    practice = tools.handle_tool(
        "hermagotchi_battle",
        {"op": "practice", "idempotency_key": "npc-prac-1"},
        client=client,
    )
    assert practice["ok"], practice
    assert practice["data"]["npc_host"]["id"] == "npc.teknium"
    assert "npc_tip" in practice["data"]

    client.wallet_bits = 5000
    buy = tools.handle_tool(
        "hermagotchi_shop",
        {"op": "buy", "item_id": "hat.binary_crown", "idempotency_key": "npc-buy-1"},
        client=client,
    )
    assert buy["ok"], buy
    assert buy["data"]["npc_host"]["context"] == "shop.purchase"

    social = tools.handle_tool("hermagotchi_social", {"op": "read"}, client=client)
    assert social["ok"], social
    assert social["data"]["npc_host"]["id"] == "npc.nous_girl"

    report = tools.handle_tool(
        "hermagotchi_social",
        {"op": "report", "target_id": "acct.x", "reason": "spam", "idempotency_key": "npc-rep-1"},
        client=client,
    )
    assert report["ok"], report
    assert report["data"]["npc_host"]["context"] == "lobby.moderation"

    lb = tools.handle_tool("hermagotchi_meta", {"op": "leaderboard"}, client=client)
    assert lb["ok"], lb
    assert lb["data"]["npc_host"]["id"] == "npc.southpaw"
    assert "turbofit" not in json.dumps(lb["data"]).lower()

    bounties = tools.handle_tool("hermagotchi_meta", {"op": "bounties"}, client=client)
    assert bounties["ok"], bounties
    assert bounties["data"]["npc_host"]["context"] == "bounty.announce"


def test_schema_token_budget_unchanged():
    # Import measure helper; skip if tiktoken missing
    tiktoken = pytest.importorskip("tiktoken")
    from schemas import TOOL_SCHEMAS

    enc = tiktoken.get_encoding("o200k_base")
    total = 0
    for schema in TOOL_SCHEMAS.values():
        total += len(enc.encode(json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))))
    assert total == 933
