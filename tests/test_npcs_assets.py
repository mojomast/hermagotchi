"""Smoke checks for launch-003 NPC cameo pack (hand-authored pixel portraits)."""
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

def test_npc_no_green_fringe_on_nous_and_don():
    import numpy as np
    from scipy import ndimage
    for key in ("nous_girl", "don_piedro", "southpaw"):
        im = np.asarray(Image.open(A / f"px3/npcs/{key}_portrait.png"))
        m = im[..., 3] > 128
        edge = m & ~ndimage.binary_erosion(m, iterations=2)
        gdom = (im[..., 1].astype(int) - np.maximum(im[..., 0], im[..., 2])) > 25
        assert (edge & gdom).sum() == 0, key

def test_teknium_hair_has_teal_not_white_dominant():
    import numpy as np
    im = np.asarray(Image.open(A / "px3/npcs/teknium_portrait.png"))
    # top-center crop ~ hair
    crop = im[40:220, 160:360]
    m = crop[..., 3] > 128
    rgb = crop[m, :3].astype(float)
    teal = (rgb[:, 1] > 90) & (rgb[:, 2] > 70) & (rgb[:, 0] < 160) & ((rgb[:, 1] + rgb[:, 2]) / 2 > rgb[:, 0] + 20)
    white = rgb.min(1) > 220
    assert teal.mean() > 0.08, teal.mean()
    assert teal.mean() > white.mean() * 0.5

def test_hand_authored_reference_and_palette_bound():
    import numpy as np
    assert NPC.get("lines_ref") == "npc_lines.json"
    for n in NPC["npcs"]:
        assert "hand-authored" in n["reference"] or "draw_npcs.py" in n["reference"]
        assert "not painterly" in n["reference"]
        assert "GenerateImage" in n["reference"] or "no GenerateImage" in n["reference"]
        assert n["source"].startswith("scripts/draw_npcs.py")
        assert "v6" not in n["source"] and "v7" not in n["source"]
        im = np.asarray(Image.open(A / n["portrait"]["path"]))
        m = im[..., 3] > 128
        cols = {tuple(c[:3].tolist()) for c in im[m]}
        assert 8 <= len(cols) <= 24, (n["id"], len(cols))
