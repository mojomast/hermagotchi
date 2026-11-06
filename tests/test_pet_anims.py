"""Pet state animation strips: coverage, bounds, compose with cosmetics."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "assets"
MAN = json.loads((A / "manifest.launch-003.json").read_text())
EXT = json.loads((A / "art_ext.launch-003.json").read_text())

STATES = ["idle", "happy", "eat", "sleep", "hurt", "attack"]

@pytest.fixture(scope="module")
def clips_by_id():
    return {c["id"]: c for c in MAN["animations"]["clips"]}

def test_every_species_palette_state_has_clip(clips_by_id):
    missing = []
    for sp, sd in EXT["species"].items():
        for pal in sd["palettes"]:
            for st in STATES:
                cid = f"{sp}.{pal}.{st}"
                if cid not in clips_by_id:
                    missing.append(cid)
    assert missing == [], f"missing clips: {missing[:10]}..."

def test_clip_meta_matches_files(clips_by_id):
    pf = MAN["animations"].get("pixel_factor", 16)
    for cid, c in clips_by_id.items():
        fp = A / c["path"]
        assert fp.is_file(), cid
        im = Image.open(fp)
        expect = (c["frame_w"] * c["frame_count"] * pf, c["frame_h"] * pf)
        assert im.size == expect, (cid, im.size, expect)
        assert len(c["frames"]) == c["frame_count"]
        for fr in c["frames"]:
            dx, dy = fr["anchor_delta"]
            assert abs(dx) <= 8 and abs(dy) <= 8

def test_anchors_stay_in_bounds_per_frame(clips_by_id):
    """Base anchors + delta must remain inside the 32 native canvas (±margin)."""
    for sp, sd in EXT["species"].items():
        anchors = sd["anchors_native"]
        pal = sd["default_palette"]
        for st in STATES:
            c = clips_by_id[f"{sp}.{pal}.{st}"]
            for fr in c["frames"]:
                dx, dy = fr["anchor_delta"]
                for name, (ax, ay) in anchors.items():
                    x, y = ax + dx, ay + dy
                    assert -4 <= x <= 35, (sp, st, name, x)
                    assert -4 <= y <= 35, (sp, st, name, y)

def test_compose_anim_frames_with_cosmetics():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import asset_px3_compose as C
    loadout = {
        "head": "hat.sudo_cap",
        "face": "face.pixel_shades",
        "back": "back.webhook_wings",
        "front": "front.rubber_duck",
        "aura": "aura.ping_pulse",
    }
    for sp in EXT["species"]:
        pal = EXT["species"][sp]["default_palette"]
        for st in STATES:
            meta = C.clip_meta(sp, pal, st)
            for fi in range(meta["frame_count"]):
                im = C.render_pet(sp, palette=pal, loadout=loadout, state=st, frame_index=fi, native=True)
                assert im.size == (32, 32)
                # must have some opaque pixels
                assert any(a > 0 for a in im.getchannel("A").tobytes())

def test_daemowl_idle_includes_blink_frame(clips_by_id):
    # frame 2 of idle is the blink — strip must differ from frame 0
    c = clips_by_id["daemowl.bark.idle"]
    pf = MAN["animations"]["pixel_factor"]
    im = Image.open(A / c["path"]).convert("RGBA")
    # down to native
    im = im.resize((c["frame_w"] * c["frame_count"], c["frame_h"]), Image.NEAREST)
    f0 = im.crop((0, 0, 32, 32))
    f2 = im.crop((64, 0, 96, 32))
    assert list(f0.tobytes()) != list(f2.tobytes())

def test_desktop_anim_contract_present():
    root = ROOT / "desktop" / "src" / "anim"
    assert (root / "petAnimContract.json").is_file()
    assert (root / "petAnimPlayer.js").is_file()
    contract = json.loads((root / "petAnimContract.json").read_text())
    assert set(STATES) <= set(contract["states"])
