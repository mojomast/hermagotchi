#!/usr/bin/env python3
"""Build launch-002 (16-bit pixel art) pack: assets/px/** + manifest.launch-002.json + art_ext.launch-002.json."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from asset_build import key_green, SRC, A
from asset_pixel import FACTOR, N, BASE_N, OUTLINE, to_native, quantize, place_native, up, palette_swap

P = A / "px"
SPECIES = {  # source, native height, native bottom, colours
  "byteblob": ("px_byteblob_v1.jpg", 72, BASE_N, 20, "Round gumdrop slime-robot, antenna, cream screen belly; sturdy/defensive."),
  "patchfox": ("px_patchfox_v1.jpg", 88, BASE_N, 24, "Sitting fox familiar, tall ears, plume tail, stitched eye patch; nimble."),
  "nullgeist": ("px_nullgeist_v1.jpg", 82, BASE_N - 4, 20, "Floating lavender glitch ghost, wisp tail, glowing eyes; status/control."),
}
PALETTES = {
  "byteblob": {"aqua": (0, 1, 1), "ember": (-170, 1.05, 1.0), "plum": (95, 0.9, 0.95), "mint": (-35, 0.8, 1.05)},
  "patchfox": {"sunset": (0, 1, 1), "arctic": (180, 0.3, 1.1), "midnight": (205, 0.75, 0.75), "rose": (-28, 0.85, 1.0)},
  "nullgeist": {"lavender": (0, 1, 1), "spectral_teal": (-100, 1.0, 1.0), "crimson": (75, 1.0, 0.95), "slate": (0, 0.25, 0.9)},
}
def protect_for(sp):
    def f(c, h, s, v):
        if s < 0.25 or v < 0.3: return True               # outline/whites/creams/greys/eye blacks
        if sp == "nullgeist" and 0.42 <= h <= 0.56: return True   # glowing cyan eyes
        if sp == "byteblob" and 0.08 <= h <= 0.17 and s < 0.4: return True  # belly screen
        return False
    return f
# native anchors (integer grid coords on the 128x128 native canvas)
ANCHORS = {
  "byteblob": {"head": [64, 43], "face": [64, 61], "back": [64, 74], "front": [64, 67], "ground": [64, 112]},
  "patchfox": {"head": [60, 44], "face": [60, 55], "back": [60, 74], "front": [60, 71], "ground": [64, 112]},
  "nullgeist": {"head": [64, 43], "face": [64, 58], "back": [64, 70], "front": [64, 76], "ground": [64, 115]},
}
SCALE = {"byteblob": 1.0, "patchfox": 0.75, "nullgeist": 1.0}
ITEMS = [  # id, slot, z, anchor, source, native width, attach, overlap, colours, desc
  ("hat.binary_crown", "head", 30, "head", "px_item_crown_v1.jpg", 36, "bottom", 4, 12, "Gold crown with magenta gem finials"),
  ("hat.propeller_beanie", "head", 30, "head", "px_item_beanie_v1.jpg", 42, "bottom", 7, 12, "Red/yellow propeller beanie"),
  ("hat.syntax_wizard", "head", 30, "head", "px_item_wizard_v1.jpg", 48, "bottom", 6, 12, "Blue wizard hat with brace/star print"),
  ("face.pixel_shades", "face", 20, "face", "item_pixel_shades_v1.jpg", 44, "cy", 0, 6, "Blocky pixel sunglasses"),
  ("face.gold_monocle", "face", 20, "face", "px_item_monocle_v1.jpg", 18, "cy", 0, 10, "Gold monocle with chain"),
  ("back.circuit_wings", "back", -10, "back", "px_item_wings_v1.jpg", 92, "cy", 0, 10, "Cyan circuit-board wings"),
  ("back.tiny_jetpack", "back", -10, "back", "px_item_jetpack_v1.jpg", 54, "cy", 0, 12, "Wide twin-tank retro jetpack"),
  ("aura.ember_halo", "aura", -30, "face", "px_item_aura_flame_v1.jpg", 86, "cy", 0, 10, "Magenta pixel flame ring"),
  ("aura.data_orbit", "aura", -30, "front", "item_aura_datacubes_v1.jpg", 92, "cy", 0, 10, "Orbit of golden data cubes"),
  ("front.cozy_scarf", "front", 40, "front", "px_item_scarf_v1.jpg", 40, "top", 0, 10, "Red striped knit scarf"),
  ("emote.heart_bubble", "emote", 50, "head", "item_emote_heart_v1.jpg", 24, "cy", 0, 6, "Heart speech-bubble emote"),
  ("habitat.plush_cushion", "habitat", -20, "ground", "item_habitat_cushion_v1.jpg", 82, "cy", 0, 8, "Mustard tufted floor cushion"),
  ("title.royal_ribbon", "title", 50, "ground", "item_title_banner_v1.jpg", 82, "cy", 0, 8, "Blank purple ribbon nameplate (client draws text)"),
]
ITEM_OFFSET = {"face.gold_monocle": (9, 0), "emote.heart_bubble": (28, -10), "title.royal_ribbon": (0, 0), "habitat.plush_cushion": (0, -2)}
CORR = {  # native (dx, dy, scale)
  "byteblob": {"front.cozy_scarf": (0, -2, 0.85), "back.tiny_jetpack": (0, -4, 1.0)},
  "patchfox": {"back.circuit_wings": (0, -2, 1.0), "back.tiny_jetpack": (0, -6, 1.0), "aura.ember_halo": (2, 2, 1.25), "aura.data_orbit": (2, 0, 1.25),
               "habitat.plush_cushion": (4, 0, 1.25), "title.royal_ribbon": (4, 0, 1.25), "front.cozy_scarf": (0, 0, 1.25)},
  "nullgeist": {"front.cozy_scarf": (0, -2, 0.9), "back.tiny_jetpack": (0, -6, 0.9), "habitat.plush_cushion": (0, 0, 0.8)},
}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(native_canvas, rel):
    p = P / rel; p.parent.mkdir(parents=True, exist_ok=True); up(native_canvas).save(p, optimize=True); return f"px/{rel}", sha(p)

def markings(body_n, kind, seed):
    al = np.asarray(body_n)[..., 3] > 0; inner = ndimage.binary_erosion(al, iterations=3)
    rng = np.random.default_rng(seed); lay = Image.new("RGBA", (N, N)); d = ImageDraw.Draw(lay)
    ys, xs = np.nonzero(inner); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    if kind == "freckles":
        for _ in range(14):
            x, y = int(rng.integers(x0, x1)), int(rng.integers(y0 + (y1 - y0) // 3, y1)); d.rectangle([x, y, x + 1, y + 1], fill=(255, 255, 255, 255))
    elif kind == "circuit":
        for _ in range(5):
            x, y = int(rng.integers(x0, x1)), int(rng.integers(y0 + (y1 - y0) // 2, y1)); L = int(rng.integers(5, 12))
            d.line([x, y, x + L, y], fill=OUTLINE + (255,)); d.line([x + L, y, x + L, y - L // 2], fill=OUTLINE + (255,)); d.point((x + L, y - L // 2 - 1), fill=(255, 230, 120, 255))
    elif kind == "stripes":
        for i in range(-4, 5):
            yy = (y0 + y1) // 2 + i * 7; d.line([x0, yy + 6, x1, yy - 6], fill=OUTLINE + (255,), width=2)
    m = np.asarray(lay).copy(); m[..., 3] = np.where(inner, m[..., 3], 0); return Image.fromarray(m, "RGBA")

def ears_front(body_n, head):
    """Patchfox ear tips drawn above headwear so hats sit between the ears (z=35)."""
    a = np.asarray(body_n).copy(); hx, hy = head
    yy, xx = np.mgrid[0:N, 0:N]; keep = (yy < hy + 1) & (np.abs(xx - hx) >= 9)
    a[~keep] = 0; return Image.fromarray(a, "RGBA")

def main():
    tmpl = json.loads((A / "manifest.json").read_text())
    man = {"schema_version": 1, "asset_pack_id": "launch-002",
           "notes": "launch-002: 16-bit pixel-art pack. Generated by Grok Bot built-in image generation (2026-11-05), converted to true pixel art (native 128x128 grid, x4 nearest upscale, binary alpha, quantized palettes) by scripts/asset_pixel_build.py. See assets/PROVENANCE.md and assets/art_ext.launch-002.json.",
           "canvas": tmpl["canvas"], "rigs": tmpl["rigs"], "species": {}, "assets": []}
    ext = {"schema": "hermagotchi-art-ext-v2", "asset_pack_id": "launch-002", "pixel_factor": FACTOR, "native_size": N,
           "outline_rgb": list(OUTLINE), "markings": ["none", "freckles", "circuit", "stripes"], "species": {}, "items": {}}
    for sp, (src, h, bot, ncol, concept) in SPECIES.items():
        n = quantize(to_native(key_green(SRC / src, strip_ground=True), height=h), ncol)
        body = place_native(n, (N - n.width) // 2, bot - n.height)
        base_rel, base_sha = save(body, f"species/{sp}_body.png")
        pals = {}
        for pn, (hs, sm, vm) in PALETTES[sp].items():
            rel, s = save(palette_swap(body, hs, sm, vm, protect_for(sp)), f"palettes/{sp}_{pn}.png"); pals[pn] = {"path": rel, "hsv_shift": [hs, sm, vm], "sha256": s}
        marks = {}
        for i, mk in enumerate(["freckles", "circuit", "stripes"]):
            rel, s = save(markings(body, mk, 2000 + i), f"markings/{sp}_{mk}.png"); marks[mk] = {"path": rel, "z": 5, "sha256": s}
        overlays = {}
        if sp == "patchfox":
            for pn, pv in pals.items():
                pimg = Image.open(A / pv["path"]).convert("RGBA").resize((N, N), Image.NEAREST)
                rel, s = save(ears_front(pimg, ANCHORS[sp]["head"]), f"overlays/patchfox_ears_{pn}.png")
                overlays[pn] = {"path": rel, "z": 35, "when_slot_equipped": "head", "sha256": s}
        norm = {k: [round(x / N, 4), round(y / N, 4)] for k, (x, y) in ANCHORS[sp].items()}
        man["species"][sp] = {"rig": "small_front_v1", "base": base_rel, "overrides": norm,
                              "features": {"marking": ext["markings"], **({"ear_type": ["pointed"], "tail_type": ["plume"]} if sp == "patchfox" else {"tail_type": ["wisp"]} if sp == "nullgeist" else {"antenna": ["nub"]})}}
        ext["species"][sp] = {"concept": concept, "source": f"source/{src}", "anchors_native": ANCHORS[sp], "item_scale": SCALE[sp],
                              "palettes": pals, "default_palette": next(iter(pals)), "markings": marks, "ear_overlays": overlays, "base_sha256": base_sha}
    for iid, slot, z, anc, src, w, attach, overlap, ncol, desc in ITEMS:
        n = quantize(to_native(key_green(SRC / src), width=w), ncol)
        x = 64 - n.width // 2
        y = {"bottom": 64 + overlap - n.height, "cy": 64 - n.height // 2, "top": 64}[attach]
        rel, s = save(place_native(n, x, y), f"items/{iid.split('.', 1)[1]}.png")
        off = ITEM_OFFSET.get(iid, (0, 0))
        man["assets"].append({"id": iid, "slot": slot, "path": rel, "rig_families": ["small_front_v1"], "z": z, "anchor": anc,
            "offset_px": [off[0] * FACTOR, off[1] * FACTOR], "scale": 1.0, **({"occludes": ["ear_base"]} if slot == "head" else {}),
            "notes": desc + ". Pixel layer; attach point at canvas (256,256); offsets are multiples of the 4px grid.", "sha256": s})
        ext["items"][iid] = {"source": f"source/{src}", "attach": attach, "colors": ncol,
            "per_species": {sp: {"compatible": True, "transform_native": list(CORR.get(sp, {}).get(iid, (0, 0, 1.0)))} for sp in SPECIES}}
    (A / "manifest.launch-002.json").write_text(json.dumps(man, indent=2) + "\n")
    (A / "art_ext.launch-002.json").write_text(json.dumps(ext, indent=2) + "\n")
    print("launch-002 built:", len(man["assets"]), "items")

if __name__ == "__main__":
    main()
