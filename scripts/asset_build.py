#!/usr/bin/env python3
"""Build Hermagotchi launch-001 layers from generated sources (chroma key -> alpha,
normalize to 512x512 rig canvas, procedural palettes/markings, manifests).
Requires numpy, Pillow, scipy (build-time only)."""
from __future__ import annotations
import colorsys, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "assets"
SRC = A / "source"
C = 512; BASE = 448

def key_green(path: Path, strip_ground: bool = False) -> Image.Image:
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    k = g - np.maximum(r, b)                      # green dominance
    alpha = np.clip(1.0 - (k - 25.0) / 70.0, 0, 1)
    m = np.maximum(r, b)
    g2 = np.where(k > 0, np.minimum(g, m + 10), g)  # despill
    out = np.dstack([r, g2, b, alpha * 255]).astype(np.uint8)
    # drop specks / thin ground lines
    lab, n = ndimage.label(alpha > 0.5)
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        h = sl[0].stop - sl[0].start; w = sl[1].stop - sl[1].start
        area = (lab[sl] == i).sum()
        if area < 40 or (h < 16 and w > 150):
            out[..., 3][lab == i] = 0
    # strip baked ground lines: bottom rows whose opaque pixels are all outline-dark
    a = out[..., 3]
    for y in (range(a.shape[0] - 1, -1, -1) if strip_ground else []):
        row = a[y] > 128
        if not row.any():
            continue
        if im[y][row].mean() < 90 or row.sum() > 0 and (im[y][row].max(-1) < 110).mean() > 0.85:
            a[max(0, y - 1):y + 1] = 0
            continue
        break
    return Image.fromarray(out, "RGBA")

def bbox(im): return im.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()

def place(im, height=None, width=None, anchor=("cx", "bottom"), at=(256, BASE)):
    im = im.crop(bbox(im)); w, h = im.size
    s = (height / h) if height else (width / w)
    im = im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    w, h = im.size
    x = at[0] - w // 2 if anchor[0] == "cx" else at[0]
    y = {"bottom": at[1] - h, "cy": at[1] - h // 2, "top": at[1]}[anchor[1]]
    cv = Image.new("RGBA", (C, C)); cv.alpha_composite(im, (int(x), int(y))); return cv

SPECIES = {  # source, height px, bottom y, concept
  "byteblob": ("byteblob_master_v1.jpg", 300, BASE, "Round gumdrop slime-robot with a cream screen belly and antenna; sturdy, defensive."),
  "patchfox": ("patchfox_master_v1.jpg", 350, BASE, "Sitting fox-like coding familiar, tall ears, huge curled tail, stitched cheek patch; nimble."),
  "nullgeist": ("nullgeist_master_v2.jpg", 330, BASE - 14, "Floating lavender glitch ghost with a curling wisp tail and glowing eyes; status/control."),
}
# palettes: hue shift (deg), sat mul, val mul applied to non-outline, non-eye pixels
PALETTES = {
  "byteblob": {"aqua": (0, 1, 1), "ember": (-170, 1.05, 1.0), "plum": (95, 0.9, 0.95), "mint": (-35, 0.8, 1.05)},
  "patchfox": {"sunset": (0, 1, 1), "arctic": (180, 0.25, 1.1), "midnight": (205, 0.75, 0.75), "rose": (-28, 0.85, 1.0)},
  "nullgeist": {"lavender": (0, 1, 1), "spectral_teal": (-100, 1.0, 1.0), "crimson": (75, 1.0, 0.95), "slate": (0, 0.25, 0.9)},
}
# anchors in normalized coords (tuned by inspection of normalized bodies)
ANCHORS = {
  "byteblob": {"head": [0.50, 0.335], "face": [0.50, 0.49], "back": [0.50, 0.60], "front": [0.50, 0.565], "ground": [0.50, 0.875]},
  "patchfox": {"head": [0.47, 0.335], "face": [0.47, 0.43], "back": [0.47, 0.58], "front": [0.47, 0.565], "ground": [0.50, 0.875]},
  "nullgeist": {"head": [0.50, 0.335], "face": [0.50, 0.47], "back": [0.50, 0.55], "front": [0.50, 0.60], "ground": [0.50, 0.90]},
}
SCALE = {"byteblob": 1.0, "patchfox": 0.82, "nullgeist": 0.9}
# items: id, slot, z, anchor, source, size(w px at scale 1), attach in item ("bottom"/"cy"/"top")
ITEMS = [
  ("hat.binary_crown", "head", 30, "head", "item_binary_crown_v1.jpg", 150, "bottom", 18, "Gold crown with magenta gem finials"),
  ("hat.propeller_beanie", "head", 30, "head", "item_propeller_beanie_v1.jpg", 175, "bottom", 30, "Red/yellow propeller beanie"),
  ("hat.syntax_wizard", "head", 30, "head", "item_wizard_hat_v1.jpg", 200, "bottom", 26, "Blue wizard hat with brace/star print"),
  ("face.pixel_shades", "face", 20, "face", "item_pixel_shades_v1.jpg", 190, "cy", 0, "Blocky pixel sunglasses"),
  ("face.gold_monocle", "face", 20, "face", "item_monocle_v1.jpg", 70, "cy", 0, "Gold monocle with chain"),
  ("back.circuit_wings", "back", -10, "back", "item_circuit_wings_v1.jpg", 360, "cy", 0, "Cyan circuit-board wings"),
  ("back.tiny_jetpack", "back", -10, "back", "item_jetpack_v1.jpg", 150, "cy", 0, "Twin-tank retro jetpack"),
  ("aura.ember_halo", "aura", -30, "face", "item_aura_flame_v1.jpg", 345, "cy", 0, "Magenta flame-wisp aura ring"),
  ("aura.data_orbit", "aura", -30, "front", "item_aura_datacubes_v1.jpg", 375, "cy", 0, "Orbit of golden data cubes"),
  ("front.cozy_scarf", "front", 40, "front", "item_scarf_v1.jpg", 175, "top", 0, "Red striped knit scarf"),
  ("emote.heart_bubble", "emote", 50, "head", "item_emote_heart_v1.jpg", 95, "cy", 0, "Heart speech-bubble emote"),
  ("habitat.plush_cushion", "habitat", -20, "ground", "item_habitat_cushion_v1.jpg", 330, "cy", 0, "Mustard tufted floor cushion"),
  ("title.royal_ribbon", "title", 50, "ground", "item_title_banner_v1.jpg", 330, "cy", 0, "Blank purple ribbon nameplate (text drawn by client)"),
]
# per-species item corrections: (dx, dy, scale multiplier); emote offset is relative
CORR = {
  "patchfox": {"hat.syntax_wizard": (0, 4, 0.85), "back.circuit_wings": (0, -10, 1.0), "aura.ember_halo": (10, 10, 1.1)},
  "nullgeist": {"front.cozy_scarf": (0, -6, 0.95), "habitat.plush_cushion": (0, 0, 0.8)},
}
ITEM_OFFSET = {"face.gold_monocle": (36, 0), "emote.heart_bubble": (110, -40), "title.royal_ribbon": (0, 34), "habitat.plush_cushion": (0, -6)}

def recolor(im: Image.Image, hs, sm, vm) -> Image.Image:
    a = np.asarray(im).astype(np.float32) / 255
    rgb = a[..., :3]; mx = rgb.max(-1); mn = rgb.min(-1); sat = (mx - mn) / np.maximum(mx, 1e-6)
    mask = (mx > 0.35) & (sat > 0.18) & (a[..., 3] > 0)
    hsv = np.asarray(Image.fromarray((rgb * 255).astype(np.uint8)).convert("HSV")).astype(np.float32)
    hsv[..., 0] = np.where(mask, (hsv[..., 0] + hs / 360 * 255) % 255, hsv[..., 0])
    hsv[..., 1] = np.where(mask, np.clip(hsv[..., 1] * sm, 0, 255), hsv[..., 1])
    hsv[..., 2] = np.where(mask, np.clip(hsv[..., 2] * vm, 0, 255), hsv[..., 2])
    out = np.asarray(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB"))
    return Image.fromarray(np.dstack([out, np.asarray(im)[..., 3]]), "RGBA")

def markings(body: Image.Image, kind: str, seed: int) -> Image.Image:
    """Procedural marking overlay clipped to the body's interior (z=5)."""
    al = np.asarray(body)[..., 3] > 200
    al = ndimage.binary_erosion(al, iterations=10)
    rng = np.random.default_rng(seed)
    lay = Image.new("RGBA", (C, C)); d = ImageDraw.Draw(lay)
    x0, y0, x1, y1 = Image.fromarray((al * 255).astype(np.uint8)).getbbox()
    if kind == "freckles":
        for _ in range(26):
            x, y, r = rng.integers(x0, x1), rng.integers(y0 + (y1 - y0) // 3, y1), rng.integers(5, 10)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 110))
    elif kind == "circuit":
        for _ in range(7):
            x, y = int(rng.integers(x0, x1)), int(rng.integers(y0 + (y1 - y0) // 2, y1))
            L = int(rng.integers(20, 50)); d.line([x, y, x + L, y, x + L, y - L // 2], fill=(20, 30, 70, 150), width=4)
            d.ellipse([x + L - 5, y - L // 2 - 5, x + L + 5, y - L // 2 + 5], fill=(255, 240, 160, 220))
    elif kind == "stripes":
        for i in range(-6, 6):
            yy = (y0 + y1) // 2 + i * 26
            d.polygon([(x0, yy), (x1, yy - 40), (x1, yy - 30), (x0, yy + 10)], fill=(20, 30, 70, 70))
    m = np.asarray(lay).copy(); m[..., 3] = m[..., 3] * al
    return Image.fromarray(m, "RGBA")

def sha(p: Path) -> str: return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    for d in ("species", "items", "palettes", "markings"): (A / d).mkdir(exist_ok=True)
    art = {"schema": "hermagotchi-art-ext-v1", "asset_pack_id": "launch-001", "species": {}, "items": {}, "markings": ["none", "freckles", "circuit", "stripes"]}
    manifest = json.loads((A / "manifest.json").read_text())
    manifest["notes"] = "launch-001: original art generated by Grok Bot built-in image generation (2026-11-05), chroma-keyed and normalized by scripts/asset_build.py. See assets/PROVENANCE.md and assets/art_ext.json (palettes, per-species transforms, compatibility)."
    manifest["rigs"] = {"small_front_v1": {"anchors": {"head": [0.50, 0.23], "face": [0.50, 0.42], "back": [0.50, 0.47], "front": [0.50, 0.66], "ground": [0.50, 0.88]}}}
    manifest["species"] = {}
    feats = {"byteblob": {"marking": ["none", "freckles", "circuit", "stripes"], "antenna": ["nub"]},
             "patchfox": {"marking": ["none", "freckles", "circuit", "stripes"], "ear_type": ["pointed"], "tail_type": ["plume"]},
             "nullgeist": {"marking": ["none", "freckles", "circuit", "stripes"], "tail_type": ["wisp"]}}
    for sp, (src, h, bot, concept) in SPECIES.items():
        body = place(key_green(SRC / src, strip_ground=True), height=h, at=(256, bot))
        p = A / "species" / f"{sp}_body.png"; body.save(p, optimize=True)
        pals = {}
        for pn, (hs, sm, vm) in PALETTES[sp].items():
            pp = A / "palettes" / f"{sp}_{pn}.png"; recolor(body, hs, sm, vm).save(pp, optimize=True)
            pals[pn] = {"path": f"palettes/{sp}_{pn}.png", "hsv_shift": [hs, sm, vm], "sha256": sha(pp)}
        marks = {}
        for i, mk in enumerate(["freckles", "circuit", "stripes"]):
            mp = A / "markings" / f"{sp}_{mk}.png"; markings(body, mk, 1000 + i).save(mp, optimize=True)
            marks[mk] = {"path": f"markings/{sp}_{mk}.png", "z": 5, "sha256": sha(mp)}
        manifest["species"][sp] = {"rig": "small_front_v1", "base": f"species/{sp}_body.png",
            "overrides": ANCHORS[sp], "features": feats[sp]}
        art["species"][sp] = {"concept": concept, "source": f"source/{src}", "anchors": ANCHORS[sp], "item_scale": SCALE[sp],
                              "palettes": pals, "default_palette": next(iter(pals)), "markings": marks,
                              "base_sha256": sha(p)}
    assets = []
    for iid, slot, z, anc, src, w, attach, overlap, desc in ITEMS:
        im = key_green(SRC / src)
        at = (256, 256 + overlap) if attach == "bottom" else (256, 256)
        lay = place(im, width=w, anchor=("cx", attach), at=at)
        name = iid.split(".", 1)[1]; p = A / "items" / f"{name}.png"; lay.save(p, optimize=True)
        compat = {sp: {"compatible": True, "transform": list(CORR.get(sp, {}).get(iid, (0, 0, 1.0)))} for sp in SPECIES}
        assets.append({"id": iid, "slot": slot, "path": f"items/{name}.png", "rig_families": ["small_front_v1"],
            "z": z, "anchor": anc, "offset_px": list(ITEM_OFFSET.get(iid, (0, 0))), "scale": 1.0,
            "notes": desc + ". Layer convention: item attach point at canvas (256,256).", "sha256": sha(p)})
        art["items"][iid] = {"source": f"source/{src}", "attach": attach, "per_species": compat}
    manifest["assets"] = assets
    (A / "manifest.launch-001.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (A / "art_ext.json").write_text(json.dumps(art, indent=2) + "\n")
    print("built", len(assets), "items,", len(SPECIES), "species")

if __name__ == "__main__":
    main()
