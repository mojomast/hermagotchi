"""Smoke checks for launch-003 NPC cameo pack (HD cinematic pass)."""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "assets"
NPC = json.loads((A / "npcs.json").read_text())
IDS = ["npc.don_piedro", "npc.nous_girl", "npc.teknium", "npc.southpaw"]

def test_npcs_schema_and_ids():
    assert NPC["schema"] == "hermagotchi-npcs-v1"
    assert NPC["asset_pack_id"] == "launch-003"
    got = [n["id"] for n in NPC["npcs"]]
    assert got == IDS
    for n in NPC["npcs"]:
        assert n["playable"] is False
        assert n["portrait"]["native"] == [128, 128]
        assert n["portrait"]["factor"] == 4
        assert "dialog" in n and n["dialog"]["native"] == [128, 128]
        assert len(n["idle"]["frames"]) == 2
        assert "cine/v3/portraits" in n["reference"]
        assert "heroes/portraits" not in n["reference"]

def test_npc_pngs_match_manifest():
    for n in NPC["npcs"]:
        for rel, meta in [
            (n["portrait"]["path"], n["portrait"]),
            (n["dialog"]["path"], n["dialog"]),
            (n["idle"]["frames"][0]["path"], n["idle"]["frames"][0]),
            (n["idle"]["frames"][1]["path"], n["idle"]["frames"][1]),
        ]:
            p = A / rel
            assert p.is_file(), rel
            im = Image.open(p)
            assert im.size == (512, 512)  # 128 * 4
            assert im.mode == "RGBA"
            # binary-ish alpha: only 0 or 255 after upscale of binary cells
            import numpy as np
            alphas = set(np.asarray(im)[..., 3].ravel().tolist())
            assert alphas <= {0, 255}, (rel, alphas)
