"""Smoke checks for launch-003 NPC cameo pack (clawpocalypse cine v3 portraits)."""
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
    assert NPC.get("lines_ref") == "npc_lines.json"
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
        assert "clawpocalypse cine v3 portrait" in n["reference"]

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

def test_npc_no_green_fringe_on_nous_and_don():
    import numpy as np
    from scipy import ndimage
    for key in ("nous_girl", "don_piedro", "southpaw"):
        im = np.asarray(Image.open(A / f"px3/npcs/{key}_portrait.png"))
        m = im[..., 3] > 128
        if not m.any():
            continue
        edge = m & ~ndimage.binary_erosion(m, iterations=2)
        gdom = (im[..., 1].astype(int) - np.maximum(im[..., 0], im[..., 2])) > 40
        # allow tiny anti-alias; block large green fringe
        assert (edge & gdom).sum() < 80, key

def test_teknium_hair_has_teal_not_white_dominant():
    import numpy as np
    im = np.asarray(Image.open(A / "px3/npcs/teknium_portrait.png"))
    crop = im[40:220, 160:360]
    m = crop[..., 3] > 128
    rgb = crop[m, :3].astype(float)
    teal = (rgb[:, 1] > 90) & (rgb[:, 2] > 70) & (rgb[:, 0] < 160) & ((rgb[:, 1] + rgb[:, 2]) / 2 > rgb[:, 0] + 20)
    white = rgb.min(1) > 220
    assert teal.mean() > 0.05, teal.mean()
    assert teal.mean() > white.mean() * 0.4

def test_cine_direct_source_and_lines_ref():
    assert NPC.get("lines_ref") == "npc_lines.json"
    for n in NPC["npcs"]:
        assert n["source"].startswith("source/cine_v3_")
        assert (A / n["source"]).is_file()
        assert "no GenerateImage" in n["reference"] or "direct Lanczos" in n["reference"]
