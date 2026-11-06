"""Every cosmetic composes on every species without crashes / empty / OOB."""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from asset_px3_compose import render_pet, EXT, MAN, N  # noqa: E402

SPECIES = sorted(EXT["species"])
ASSETS = MAN["assets"]


def test_cosmetics_count_and_slots():
    assert len(ASSETS) >= 70  # 13 existing + ~60 new
    slots = {a["slot"] for a in ASSETS}
    assert {"head", "face", "back", "front", "aura"} <= slots


def test_every_item_has_per_species_transforms():
    for a in ASSETS:
        per = EXT["items"][a["id"]]["per_species"]
        for sp in SPECIES:
            assert sp in per, (a["id"], sp)
            dx, dy, sm = per[sp]["transform_native"]
            assert per[sp]["compatible"] is True
            assert isinstance(dx, (int, float)) and isinstance(dy, (int, float))


def test_hand_anchor_exists_for_held_props():
    for sp in SPECIES:
        assert "hand" in EXT["species"][sp]["anchors_native"]
    held = [a for a in ASSETS if a["id"].startswith("front.") and a["anchor"] == "hand"]
    assert len(held) >= 10


@pytest.mark.parametrize("sp", SPECIES)
def test_compose_all_items_on_species(sp):
    for a in ASSETS:
        im = render_pet(sp, loadout={a["slot"]: a["id"]}, native=True)
        arr = np.asarray(im)
        assert arr.shape == (N, N, 4)
        assert arr[..., 3].sum() > 0
        # no pixels outside canvas (tautology on native paste) — ensure item path exists
        assert (ROOT / "assets" / a["path"]).is_file()


def test_daemowl_face_keeps_third_eye_visible():
    """Shades should not fully paint over forehead third eye."""
    body = render_pet("daemowl", loadout={}, native=True)
    with_shades = render_pet("daemowl", loadout={"face": "face.regex_rims"}, native=True)
    b = np.asarray(body)
    s = np.asarray(with_shades)
    # amber third eye roughly y=11..13 x=14..16 — some amber should remain
    crop_b = b[10:14, 13:18]
    crop_s = s[10:14, 13:18]
    amber = lambda a: ((a[..., 0] > 200) & (a[..., 1] > 100) & (a[..., 2] < 50) & (a[..., 3] > 128)).sum()
    assert amber(crop_b) >= 3
    assert amber(crop_s) >= 2  # still visible above shades


def test_dressed_pet_layers_without_crash():
    lo = {
        "head": "hat.cron_crown",
        "face": "face.hex_specs",
        "back": "back.caped_crusader",
        "front": "front.cache_scarf",
        "aura": "aura.ping_pulse",
    }
    for sp in SPECIES:
        im = render_pet(sp, loadout=lo, native=True)
        assert np.asarray(im)[..., 3].sum() > 0
