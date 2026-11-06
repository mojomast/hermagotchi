#!/usr/bin/env python3
"""launch-002 compositor: composites on the native pixel grid, then x4 nearest upscale,
so every layer shares one uniform pixel grid."""
from __future__ import annotations
import argparse, json, random
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]; A = ROOT / "assets"
MAN = json.loads((A / "manifest.launch-002.json").read_text()); EXT = json.loads((A / "art_ext.launch-002.json").read_text())
F = EXT["pixel_factor"]; N = EXT["native_size"]; ITEMS = {a["id"]: a for a in MAN["assets"]}
SLOTS = ["head", "face", "back", "front", "aura", "emote", "habitat", "title"]; _c = {}

def _n(rel):
    if rel not in _c: _c[rel] = Image.open(A / rel).convert("RGBA").resize((N, N), Image.NEAREST)
    return _c[rel]

def _item(cv, it, sp):
    s = EXT["species"][sp]; ax, ay = s["anchors_native"][it["anchor"]]
    dx, dy, sm = EXT["items"][it["id"]]["per_species"][sp]["transform_native"]
    k = it["scale"] * s["item_scale"] * sm; lay = _n(it["path"])
    if abs(k - 1) > 1e-3:
        size = round(N * k); lay = lay.resize((size, size), Image.NEAREST)
    ox = ax + it["offset_px"][0] // F + dx - round(64 * k); oy = ay + it["offset_px"][1] // F + dy - round(64 * k)
    cv.paste(lay, (ox, oy), lay)

def render_pet(species, appearance_seed=0, palette=None, marking="none", loadout=None, native=False):
    loadout = loadout or {}
    for iid in loadout.values():
        if iid not in ITEMS: raise ValueError(f"unknown asset id {iid!r}")
    s = EXT["species"][species]; palette = palette or s["default_palette"]
    seq = [(0, 0, ("img", s["palettes"][palette]["path"]))]
    if marking != "none": seq.append((5, 0, ("img", s["markings"][marking]["path"])))
    if "head" in loadout and palette in s.get("ear_overlays", {}): seq.append((35, 0, ("img", s["ear_overlays"][palette]["path"])))
    seq += [(ITEMS[i]["z"], 1, ("item", ITEMS[i])) for i in loadout.values()]
    cv = Image.new("RGBA", (N, N))
    for _, _, (kind, x) in sorted(seq, key=lambda t: (t[0], t[1])):
        if kind == "img": im = _n(x); cv.paste(im, (0, 0), im)
        else: _item(cv, x, species)
    return cv if native else cv.resize((N * F, N * F), Image.NEAREST)

def seeded_look(seed):
    r = random.Random(seed); sp = r.choice(sorted(EXT["species"]))
    pal = r.choice(sorted(EXT["species"][sp]["palettes"])); mk = r.choice(EXT["markings"]); by = {}
    for a in MAN["assets"]: by.setdefault(a["slot"], []).append(a["id"])
    lo = {s: r.choice(by[s]) for s in SLOTS if s in by and r.random() < (0.35 if s in ("emote", "title") else 0.55)}
    return dict(species=sp, appearance_seed=seed, palette=pal, marking=mk, loadout=lo)

def contact_sheet(n=100, cols=10, cell=256, out=A / "contact_sheet_100_launch-002.png"):
    rows = (n + cols - 1) // cols; sheet = Image.new("RGB", (cols * cell, rows * (cell + 14)), (236, 232, 245)); d = ImageDraw.Draw(sheet); looks = []
    for i in range(n):
        lk = seeded_look(i); looks.append(lk); im = render_pet(**lk, native=True).resize((cell, cell), Image.NEAREST)
        x, y = (i % cols) * cell, (i // cols) * (cell + 14); sheet.paste(im, (x, y), im); d.text((x + 4, y + cell), f"#{i} {lk['species'][:5]} {lk['palette'][:6]}", fill=(40, 40, 60))
    sheet.save(out, optimize=True); return looks

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=100); a = ap.parse_args()
    looks = contact_sheet(a.n); keys = {json.dumps([l["species"], l["palette"], l["marking"], l["loadout"]], sort_keys=True) for l in looks}
    print(f"rendered {len(looks)} looks, {len(keys)} distinct")
