"""Every cosmetic composes on every species without crashes / empty / OOB."""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

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


# ---------- launch-003 fit contract (W10-X) ----------

COMPOSE_SNAPSHOT = ROOT / "desktop" / "src" / "ui" / "logic" / "composeAnchors.json"
PIXEL_FACTOR = EXT["pixel_factor"]
BODY_CENTER = (16, 16)
FACE_EYE_EXCLUDE = {"face.happy_path", "face.pixel_mustache", "face.privacy_mask"}

_bbox_cache: dict[str, tuple[float, float, float, float]] = {}


def _content_bbox(rel: str):
    """Native-grid content bounds of a 512px (32x16) cosmetic layer."""
    if rel not in _bbox_cache:
        arr = np.asarray(Image.open(ROOT / "assets" / rel).convert("RGBA"))
        ys, xs = np.where(arr[..., 3] > 8)
        assert len(xs), rel
        _bbox_cache[rel] = (
            xs.min() / PIXEL_FACTOR,
            ys.min() / PIXEL_FACTOR,
            xs.max() / PIXEL_FACTOR,
            ys.max() / PIXEL_FACTOR,
        )
    return _bbox_cache[rel]


def _placed(item, species):
    """Return (content bbox, center) in native 32-grid coordinates, mirroring _item()."""
    sp = EXT["species"][species]
    asset = next(a for a in ASSETS if a["id"] == item)
    ax, ay = sp["anchors_native"][asset["anchor"]]
    dx, dy, sm = EXT["items"][item]["per_species"][species]["transform_native"]
    k = asset["scale"] * sp["item_scale"] * sm
    cx = ax + asset["offset_px"][0] // PIXEL_FACTOR + dx
    cy = ay + asset["offset_px"][1] // PIXEL_FACTOR + dy
    x0, y0, x1, y1 = _content_bbox(asset["path"])
    bbox = (
        cx + (x0 - 16) * k,
        cy + (y0 - 16) * k,
        cx + (x1 - 16) * k,
        cy + (y1 - 16) * k,
    )
    return bbox, (cx, cy), k


def test_compose_snapshot_matches_art_ext():
    data = json.loads(COMPOSE_SNAPSHOT.read_text())
    assert data["asset_pack_id"] == EXT["asset_pack_id"]
    assert data["native_size"] == N
    for sp in SPECIES:
        assert data["species"][sp]["anchors_native"] == EXT["species"][sp]["anchors_native"]
        assert data["species"][sp]["item_scale"] == EXT["species"][sp]["item_scale"]
    for item in EXT["items"]:
        for sp in SPECIES:
            assert data["items"][item]["per_species"][sp] == list(
                EXT["items"][item]["per_species"][sp]["transform_native"]
            )


@pytest.mark.parametrize("sp", SPECIES)
def test_head_items_sit_above_the_face(sp):
    sp_data = EXT["species"][sp]
    head_y = sp_data["anchors_native"]["head"][1]
    face_y = sp_data["anchors_native"]["face"][1]
    for asset in ASSETS:
        if asset["slot"] != "head":
            continue
        (_, top, _, bottom), _, _ = _placed(asset["id"], sp)
        assert bottom <= face_y, (sp, asset["id"], bottom, face_y)
        assert bottom >= head_y - 1, (sp, asset["id"], bottom, head_y)
        assert bottom <= head_y + 2.5, (sp, asset["id"], bottom, head_y)
        assert top >= -0.001, (sp, asset["id"], top)


@pytest.mark.parametrize("sp", SPECIES)
def test_eye_band_face_items_cover_the_face_anchor(sp):
    face_y = EXT["species"][sp]["anchors_native"]["face"][1]
    for asset in ASSETS:
        if asset["slot"] != "face" or asset["id"] in FACE_EYE_EXCLUDE:
            continue
        (_, top, _, bottom), _, _ = _placed(asset["id"], sp)
        center = (top + bottom) / 2
        assert abs(center - face_y) <= 3, (sp, asset["id"], center, face_y)


@pytest.mark.parametrize("sp", SPECIES)
def test_back_items_wrap_the_shoulders(sp):
    back_y = EXT["species"][sp]["anchors_native"]["back"][1]
    for asset in ASSETS:
        if asset["slot"] != "back":
            continue
        (_, top, _, bottom), _, _ = _placed(asset["id"], sp)
        center = (top + bottom) / 2
        assert abs(center - back_y) <= 2, (sp, asset["id"], center, back_y)


@pytest.mark.parametrize("sp", SPECIES)
def test_hand_props_centre_on_the_hand_anchor(sp):
    hand_y = EXT["species"][sp]["anchors_native"]["hand"][1]
    hand_x = EXT["species"][sp]["anchors_native"]["hand"][0]
    for asset in ASSETS:
        if asset["slot"] != "front" or asset["anchor"] != "hand":
            continue
        (left, top, right, bottom), _, _ = _placed(asset["id"], sp)
        assert abs((top + bottom) / 2 - hand_y) <= 2, (sp, asset["id"])
        assert abs((left + right) / 2 - hand_x) <= 3, (sp, asset["id"])


@pytest.mark.parametrize("sp", SPECIES)
def test_auras_surround_the_body_centre(sp):
    for asset in ASSETS:
        if asset["slot"] != "aura":
            continue
        (left, top, right, bottom), _, _ = _placed(asset["id"], sp)
        assert abs((left + right) / 2 - BODY_CENTER[0]) <= 1.5, (sp, asset["id"])
        assert abs((top + bottom) / 2 - BODY_CENTER[1]) <= 1.5, (sp, asset["id"])
