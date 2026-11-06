#!/usr/bin/env python3
"""Deterministic Hermagotchi compositor + seeded contact sheet.
render_pet(species, appearance_seed, palette, marking, loadout) -> 512x512 RGBA."""
from __future__ import annotations
import argparse, json, random
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]; A = ROOT / "assets"
MAN = json.loads((A / "manifest.launch-001.json").read_text()); EXT = json.loads((A / "art_ext.json").read_text())
ITEMS = {a["id"]: a for a in MAN["assets"]}
SLOTS = ["head", "face", "back", "front", "aura", "emote", "habitat", "title"]
_cache: dict[str, Image.Image] = {}

def _img(rel):
    if rel not in _cache: _cache[rel] = Image.open(A / rel).convert("RGBA")
    return _cache[rel]

def _place(canvas, item, sp):
    spx = EXT["species"][sp]; ax, ay = spx["anchors"][item["anchor"]]
    dx, dy, sm = EXT["items"][item["id"]]["per_species"][sp]["transform"]
    s = item["scale"] * spx["item_scale"] * sm
    lay = _img(item["path"])
    if abs(s - 1) > 1e-3: lay = lay.resize((round(512 * s), round(512 * s)), Image.LANCZOS)
    ox = round(ax * 512 + item["offset_px"][0] + dx - 256 * s); oy = round(ay * 512 + item["offset_px"][1] + dy - 256 * s)
    tmp = Image.new("RGBA", (512, 512)); tmp.paste(lay, (ox, oy), lay); canvas.alpha_composite(tmp)

def render_pet(species, appearance_seed=0, palette=None, marking="none", loadout=None):
    loadout = loadout or {}
    for iid in loadout.values():
        if iid not in ITEMS: raise ValueError(f"unknown asset id {iid!r}")  # allowlist only
    sp = EXT["species"][species]; palette = palette or sp["default_palette"]
    layers = [(ITEMS[i]["z"], ITEMS[i]) for i in loadout.values()]
    cv = Image.new("RGBA", (512, 512))
    body = [(0, ("body", sp["palettes"][palette]["path"]))]
    if marking != "none": body.append((5, ("mark", sp["markings"][marking]["path"])))
    seq = sorted([(z, 0, x) for z, x in body] + [(z, 1, it) for z, it in layers], key=lambda t: (t[0], t[1]))
    for z, kind, x in seq:
        if kind == 0: cv.alpha_composite(_img(x[1]))
        else: _place(cv, x, species)
    return cv

def seeded_look(seed):
    r = random.Random(seed); sp = r.choice(sorted(EXT["species"]))
    pal = r.choice(sorted(EXT["species"][sp]["palettes"])); mk = r.choice(EXT["markings"])
    by = {}
    for a in MAN["assets"]: by.setdefault(a["slot"], []).append(a["id"])
    lo = {s: r.choice(by[s]) for s in SLOTS if s in by and r.random() < (0.35 if s in ("emote", "title") else 0.55)}
    return dict(species=sp, appearance_seed=seed, palette=pal, marking=mk, loadout=lo)

def contact_sheet(n=100, cols=10, cell=192, out=A / "contact_sheet_100.png", bg=(236, 232, 245)):
    rows = (n + cols - 1) // cols; sheet = Image.new("RGB", (cols * cell, rows * (cell + 14)), bg); d = ImageDraw.Draw(sheet)
    looks = []
    for i in range(n):
        lk = seeded_look(i); looks.append(lk)
        im = render_pet(**lk).resize((cell, cell), Image.LANCZOS)
        x, y = (i % cols) * cell, (i // cols) * (cell + 14)
        sheet.paste(im, (x, y), im); d.text((x + 4, y + cell), f"#{i} {lk['species'][:5]} {lk['palette'][:6]}", fill=(40, 40, 60))
    sheet.save(out, optimize=True); return looks

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=100); ap.add_argument("--out", default=str(A / "contact_sheet_100.png"))
    a = ap.parse_args(); looks = contact_sheet(a.n, out=Path(a.out))
    keys = {json.dumps(l, sort_keys=True, default=str).split('"appearance_seed"')[0] + json.dumps([l["palette"], l["marking"], l["loadout"]], sort_keys=True) for l in looks}
    print(f"rendered {len(looks)} looks, {len(keys)} distinct -> {a.out}")
