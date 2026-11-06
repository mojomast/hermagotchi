#!/usr/bin/env python3
"""Build launch-003 (low-res handheld pixel art, native 32x32, x16) -> assets/px3/**,
manifest.launch-003.json, art_ext.launch-003.json. All sources are fresh px3_* generations."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image
from asset_build import key_green, SRC, A
from asset_px3 import FACTOR, N, BASE_N, OUTLINE, to_native_mode, place_native, up
from asset_pixel import palette_swap

P = A / "px3"
SPECIES = {  # source, native height, bottom row (exclusive), colours, concept
  "byteblob": ("px3_byteblob_v1.jpg", 22, BASE_N, 8, "Boxy robot-slime with a black visor screen for a face, stubby legs, bent antenna with a yellow tip."),
  "patchfox": ("px3_patchfox_v1.jpg", 23, BASE_N, 10, "Standing fox critter with huge triangle ears, white-tipped bushy tail and a blue chest patch."),
  "nullgeist": ("px3_nullgeist_v1.jpg", 22, BASE_N - 1, 12, "Hooded sheet-ghost with a jagged hem, one glowing cyan eye and one magenta X eye."),
}
# hand pixel cleanup at native res (sprite-local x, y) -> rgb: restores eyes lost at 32px
FIX = {
  "patchfox": {(5, 10): OUTLINE, (9, 10): OUTLINE},
  "nullgeist": {(10, 7): (255, 40, 200), (12, 7): (255, 40, 200), (11, 8): (255, 40, 200), (10, 9): (255, 40, 200), (12, 9): (255, 40, 200)},
}
PALETTES = {
  "byteblob": {"teal": (0, 1, 1), "brick": (175, 1.0, 1.0), "grape": (80, 0.9, 1.0), "lime": (-75, 0.9, 1.05)},
  "patchfox": {"rust": (0, 1, 1), "arctic": (180, 0.6, 1.0), "dusk": (230, 0.7, 0.8), "moss": (60, 0.8, 0.85)},
  "nullgeist": {"violet": (0, 1, 1), "ember": (110, 1.0, 1.0), "abyss": (-50, 1.0, 0.8), "jade": (-110, 0.8, 0.9)},
}
def protect_for(sp):
    def f(c, h, s, v):
        if s < 0.3 or v < 0.3: return True                       # outline, whites, visor black
        if sp == "byteblob" and v > 0.9 and s < 0.6: return True  # cyan eye glints
        if sp == "byteblob" and 0.1 <= h <= 0.18: return True     # antenna tip
        if sp == "patchfox" and 0.55 <= h <= 0.7: return True     # blue chest patch
        if sp == "nullgeist" and (0.45 <= h <= 0.56 or (0.84 <= h <= 0.95 and s > 0.7)): return True  # cyan eye + X eye
        return False
    return f
ANCHORS = {  # native 32-grid ints
  "byteblob": {"head": [16, 11], "face": [16, 16], "back": [16, 17], "front": [16, 23], "ground": [16, 28]},
  "patchfox": {"head": [15, 11], "face": [15, 15], "back": [15, 20], "front": [15, 18], "ground": [16, 28]},
  "nullgeist": {"head": [16, 9], "face": [16, 13], "back": [16, 16], "front": [16, 19], "ground": [16, 28]},
}
ITEMS = [  # id, slot, z, anchor, source, native width, attach, overlap, colours, manifest scale, desc
  ("hat.binary_crown", "head", 30, "head", "px3_item_crown_v1.jpg", 8, "bottom", 1, 4, 1.0, "Chunky gold crown with a red gem"),
  ("hat.propeller_beanie", "head", 30, "head", "px3_item_beanie_v1.jpg", 9, "bottom", 2, 5, 1.0, "Red/yellow propeller cap"),
  ("hat.syntax_wizard", "head", 30, "head", "px3_item_wizard_v1.jpg", 10, "bottom", 2, 4, 1.0, "Blue wizard hat with star dots"),
  ("face.pixel_shades", "face", 20, "face", "px3_item_shades_v1.jpg", 12, "cy", 0, 3, 1.0, "Black shades with glints"),
  ("face.gold_monocle", "face", 20, "face", "px3_item_monocle_v1.jpg", 5, "cy", 0, 4, 1.0, "Gold monocle on a stalk"),
  ("back.circuit_wings", "back", -10, "back", "px3_item_wings_v1.jpg", 23, "cy", 0, 4, 1.0, "Blocky cyan robot wings"),
  ("back.tiny_jetpack", "back", -10, "back", "px3_item_jetpack_v1.jpg", 22, "cy", 0, 5, 1.0, "Wide twin-tank jetpack"),
  ("aura.ember_halo", "aura", -30, "face", "px3_item_aura_flame_v1.jpg", 22, "cy", 0, 3, 1.25, "Magenta pixel flame ring"),
  ("aura.data_orbit", "aura", -30, "front", "px3_item_aura_orbit_v1.jpg", 22, "cy", 0, 3, 1.25, "Orbit of yellow/orange data bits"),
  ("front.cozy_scarf", "front", 40, "front", "px3_item_scarf_v1.jpg", 10, "top", 0, 4, 1.0, "Red striped scarf"),
  ("emote.heart_bubble", "emote", 50, "head", "px3_item_emote_v1.jpg", 7, "cy", 0, 3, 1.0, "Heart speech-bubble emote"),
  ("habitat.plush_cushion", "habitat", -20, "ground", "px3_item_cushion_v1.jpg", 18, "cy", 0, 4, 1.0, "Mustard floor cushion"),
  ("title.royal_ribbon", "title", 50, "ground", "px3_item_ribbon_v1.jpg", 16, "cy", 0, 4, 1.0, "Blank purple ribbon (client draws text)"),
]
ITEM_OFFSET = {"face.gold_monocle": (3, 0), "emote.heart_bubble": (8, -3), "habitat.plush_cushion": (0, -1), "title.royal_ribbon": (0, 2)}
CORR = {
  "byteblob": {"back.circuit_wings": (0, -2, 1.0), "back.tiny_jetpack": (0, 2, 1.0)},
  "patchfox": {"back.tiny_jetpack": (0, 0, 1.0), "front.cozy_scarf": (0, -1, 1.0)},
  "nullgeist": {"back.tiny_jetpack": (0, 2, 1.0), "front.cozy_scarf": (0, -1, 1.0)},
}
MARKINGS = ["none", "freckles", "stripes", "spot"]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(cv, rel):
    p = P / rel; p.parent.mkdir(parents=True, exist_ok=True); up(cv).save(p, optimize=True); return f"px3/{rel}", sha(p)

def markings(body, kind):
    """Sparse native-pixel markings so they read at 32px without turning into noise."""
    a = np.asarray(body); m = a[..., 3] > 0
    inner = m & (a[..., :3].max(-1) > 90) & ~np.all(a[..., :3] == OUTLINE, -1)
    ys, xs = np.nonzero(inner); y0, y1 = ys.min(), ys.max(); cx = int(round(xs.mean()))
    lay = np.zeros_like(a); W = (255, 255, 255, 255); D = OUTLINE + (255,)
    def put(x, y, c):
        if 0 <= y < N and 0 <= x < N and inner[y, x]: lay[y, x] = c
    if kind == "freckles":
        yy = y0 + (y1 - y0) * 2 // 3
        for dx in (-4, -3, 3, 4): put(cx + dx, yy + (abs(dx) % 2), W)
    elif kind == "stripes":
        for yy in (y1 - 2, y1 - 4, y1 - 6):
            for dx in range(-2, 3): put(cx + dx, yy, D)
    elif kind == "spot":
        yy = y0 + (y1 - y0) // 2
        for dx in (0, 1):
            for dy in (0, 1): put(cx + 3 + dx, yy + dy, W)
    return Image.fromarray(lay, "RGBA")

def ears_front(body, head):
    """Patchfox ear tips drawn above headwear (z=35) so hats sit between the ears."""
    a = np.asarray(body).copy(); hx, hy = head; yy, xx = np.mgrid[0:N, 0:N]
    a[~((yy < hy) & (np.abs(xx - hx) >= 3))] = 0; return Image.fromarray(a, "RGBA")

def main():
    tmpl = json.loads((A / "manifest.json").read_text())
    man = {"schema_version": 1, "asset_pack_id": "launch-003",
           "notes": "launch-003: low-res handheld pixel art (native 32x32 grid, x16 nearest upscale, binary alpha, 8-12 colours/species, 3-5/item). All fresh Grok Bot built-in generations 2026-11-05; see assets/PROVENANCE.md and assets/art_ext.launch-003.json.",
           "canvas": tmpl["canvas"], "rigs": tmpl["rigs"], "species": {}, "assets": []}
    ext = {"schema": "hermagotchi-art-ext-v2", "asset_pack_id": "launch-003", "pixel_factor": FACTOR, "native_size": N,
           "outline_rgb": list(OUTLINE), "markings": MARKINGS, "species": {}, "items": {}}
    for sp, (src, h, bot, ncol, concept) in SPECIES.items():
        n = to_native_mode(key_green(SRC / src), ncol, height=h, min_area_frac=0.02)
        arr = np.asarray(n).copy()
        for (x, y), c in FIX.get(sp, {}).items():
            if arr[y, x, 3]: arr[y, x, :3] = c
        body = place_native(Image.fromarray(arr, "RGBA"), (N - n.width) // 2, bot - n.height)
        base_rel, base_sha = save(body, f"species/{sp}_body.png")
        pals, marks, ears = {}, {}, {}
        for pn, (hs, sm, vm) in PALETTES[sp].items():
            pimg = palette_swap(body, hs, sm, vm, protect_for(sp)); rel, s = save(pimg, f"palettes/{sp}_{pn}.png")
            pals[pn] = {"path": rel, "hsv_shift": [hs, sm, vm], "sha256": s}
            if sp == "patchfox":
                rel, s = save(ears_front(pimg, ANCHORS[sp]["head"]), f"overlays/patchfox_ears_{pn}.png"); ears[pn] = {"path": rel, "z": 35, "when_slot_equipped": "head", "sha256": s}
        for mk in MARKINGS[1:]:
            rel, s = save(markings(body, mk), f"markings/{sp}_{mk}.png"); marks[mk] = {"path": rel, "z": 5, "sha256": s}
        man["species"][sp] = {"rig": "small_front_v1", "base": base_rel,
            "overrides": {k: [round(x / N, 4), round(y / N, 4)] for k, (x, y) in ANCHORS[sp].items()},
            "features": {"marking": MARKINGS, **({"ear_type": ["giant"], "tail_type": ["brush"]} if sp == "patchfox" else {"hood": ["pointed"], "eye_style": ["mismatched"]} if sp == "nullgeist" else {"face": ["visor"], "antenna": ["bent"]})}}
        ext["species"][sp] = {"concept": concept, "source": f"source/{src}", "anchors_native": ANCHORS[sp], "item_scale": 1.0,
            "palettes": pals, "default_palette": next(iter(pals)), "markings": marks, "ear_overlays": ears, "base_sha256": base_sha}
    for iid, slot, z, anc, src, w, attach, overlap, ncol, scale, desc in ITEMS:
        n = to_native_mode(key_green(SRC / src), ncol, width=w)
        x = 16 - n.width // 2; y = {"bottom": 16 + overlap - n.height, "cy": 16 - n.height // 2, "top": 16}[attach]
        rel, s = save(place_native(n, x, y), f"items/{iid.split('.', 1)[1]}.png"); off = ITEM_OFFSET.get(iid, (0, 0))
        man["assets"].append({"id": iid, "slot": slot, "path": rel, "rig_families": ["small_front_v1"], "z": z, "anchor": anc,
            "offset_px": [off[0] * FACTOR, off[1] * FACTOR], "scale": scale, **({"occludes": ["ear_base"]} if slot == "head" else {}),
            "notes": desc + ". 32-grid pixel layer; attach point at canvas (256,256); offsets are multiples of 16px.", "sha256": s})
        ext["items"][iid] = {"source": f"source/{src}", "attach": attach, "colors": ncol,
            "per_species": {sp: {"compatible": True, "transform_native": list(CORR.get(sp, {}).get(iid, (0, 0, 1.0)))} for sp in SPECIES}}
    (A / "manifest.launch-003.json").write_text(json.dumps(man, indent=2) + "\n")
    (A / "art_ext.launch-003.json").write_text(json.dumps(ext, indent=2) + "\n")
    print("launch-003 built:", len(man["assets"]), "items")

if __name__ == "__main__":
    main()
