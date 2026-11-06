#!/usr/bin/env python3
"""launch-003 compositor (generic native-grid): composites on the native pixel grid, then x4 nearest upscale,
so every layer shares one uniform pixel grid.

Supports pet state animation frames via art_ext/manifest animations{}:
cosmetics follow per-frame anchor_delta (bob/lunge/recoil); aura items keep their 2-frame cycle.
"""
from __future__ import annotations
import argparse, json, random
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]; A = ROOT / "assets"
MAN = json.loads((A / "manifest.launch-003.json").read_text()); EXT = json.loads((A / "art_ext.launch-003.json").read_text())
F = EXT["pixel_factor"]; N = EXT["native_size"]; ITEMS = {a["id"]: a for a in MAN["assets"]}
SLOTS = ["head", "face", "back", "front", "aura", "emote", "habitat", "title"]; _c = {}
ANIMS = (EXT.get("animations") or {}).get("clips") or {}

def _n(rel):
    if rel not in _c: _c[rel] = Image.open(A / rel).convert("RGBA").resize((N, N), Image.NEAREST)
    return _c[rel]

def _strip_frame(rel: str, index: int, frame_w: int = N) -> Image.Image:
    """Extract one native frame from a horizontal strip (hi-res or native)."""
    key = f"{rel}#f{index}"
    if key in _c:
        return _c[key]
    im = Image.open(A / rel).convert("RGBA")
    # detect scale
    if im.size[1] == N:
        fw = frame_w
    elif im.size[1] % N == 0:
        scale = im.size[1] // N
        fw = frame_w * scale
        im = im.resize((im.size[0] // scale, im.size[1] // scale), Image.NEAREST)
        fw = frame_w
    else:
        im = im.resize((im.size[0] * N // im.size[1], N), Image.NEAREST)
        fw = frame_w
    x0 = index * fw
    fr = im.crop((x0, 0, x0 + fw, N))
    if fr.size != (N, N):
        fr = fr.resize((N, N), Image.NEAREST)
    _c[key] = fr
    return fr

def clip_id(species: str, palette: str, state: str) -> str:
    return f"{species}.{palette}.{state}"

def clip_meta(species: str, palette: str, state: str) -> dict:
    cid = clip_id(species, palette, state)
    if cid not in ANIMS:
        raise KeyError(f"missing animation clip {cid}")
    return ANIMS[cid]

def _item(cv, it, sp, anchor_delta=(0, 0), aura_frame=0):
    s = EXT["species"][sp]
    ax, ay = s["anchors_native"][it["anchor"]]
    ax = ax + int(anchor_delta[0]); ay = ay + int(anchor_delta[1])
    dx, dy, sm = EXT["items"][it["id"]]["per_species"][sp]["transform_native"]
    k = it["scale"] * s["item_scale"] * sm
    # aura 2-frame cycle
    path = it["path"]
    meta = EXT["items"].get(it["id"], {})
    frames = meta.get("frames")
    if it.get("slot") == "aura" and isinstance(frames, list) and frames:
        path = frames[aura_frame % len(frames)]["path"]
    lay = _n(path)
    if abs(k - 1) > 1e-3:
        size = round(N * k); lay = lay.resize((size, size), Image.NEAREST)
    ox = ax + it["offset_px"][0] // F + dx - round(N // 2 * k)
    oy = ay + it["offset_px"][1] // F + dy - round(N // 2 * k)
    cv.paste(lay, (ox, oy), lay)

def render_pet(species, appearance_seed=0, palette=None, marking="none", loadout=None, native=False,
               state: str | None = None, frame_index: int = 0):
    """Render a pet. If state is set, use that animation clip frame as the body and
    apply the frame's anchor_delta to all cosmetic anchors (cosmetics follow bob/lunge)."""
    loadout = loadout or {}
    for iid in loadout.values():
        if iid not in ITEMS: raise ValueError(f"unknown asset id {iid!r}")
    s = EXT["species"][species]; palette = palette or s["default_palette"]
    anchor_delta = (0, 0)
    body_path = s["palettes"][palette]["path"]
    body_img = None
    if state:
        meta = clip_meta(species, palette, state)
        fi = int(frame_index) % int(meta["frame_count"])
        body_img = _strip_frame(meta["path"], fi, meta.get("frame_native", N))
        fr = meta["frames"][fi]
        ad = fr.get("anchor_delta") or [0, 0]
        anchor_delta = (int(ad[0]), int(ad[1]))
    seq = [(0, 0, ("body", body_img if body_img is not None else body_path))]
    if marking != "none": seq.append((5, 0, ("img", s["markings"][marking]["path"])))
    if "head" in loadout and palette in s.get("ear_overlays", {}):
        seq.append((35, 0, ("img", s["ear_overlays"][palette]["path"])))
    seq += [(ITEMS[i]["z"], 1, ("item", ITEMS[i])) for i in loadout.values()]
    cv = Image.new("RGBA", (N, N))
    aura_frame = int(frame_index)  # auras keep 2-frame cycle tied to time
    for _, _, (kind, x) in sorted(seq, key=lambda t: (t[0], t[1])):
        if kind == "body":
            im = x if isinstance(x, Image.Image) else _n(x)
            # When body already includes bob shift, paste at 0,0 (delta is for anchors only).
            cv.paste(im, (0, 0), im)
        elif kind == "img":
            im = _n(x)
            # markings / ears follow bob
            cv.paste(im, (int(anchor_delta[0]), int(anchor_delta[1])), im)
        else:
            _item(cv, x, species, anchor_delta=anchor_delta, aura_frame=aura_frame)
    return cv if native else cv.resize((N * F, N * F), Image.NEAREST)

def seeded_look(seed):
    r = random.Random(seed); sp = r.choice(sorted(EXT["species"]))
    pal = r.choice(sorted(EXT["species"][sp]["palettes"])); mk = r.choice(EXT["markings"]); by = {}
    for a in MAN["assets"]: by.setdefault(a["slot"], []).append(a["id"])
    lo = {s: r.choice(by[s]) for s in SLOTS if s in by and r.random() < (0.35 if s in ("emote", "title") else 0.55)}
    return dict(species=sp, appearance_seed=seed, palette=pal, marking=mk, loadout=lo)

FIT_GRID_ITEMS = [
    ("head", "hat.bloom_filter"),
    ("face", "face.hex_specs"),
    ("back", "back.circuit_wings"),
    ("front", "front.pointer_wand"),
    ("aura", "aura.ping_pulse"),
]


def render_fit_grid(out=A / "preview" / "cosmetics_fit_grid_v2.png", cell=160,
                    species=None, items=None):
    """Render all species x one representative cosmetic per slot.

    Writes a labelled PNG grid with native-nearest upscaling so hat / face /
    back / hand / aura anchor fit is easy to review. Used by W10-X.
    """
    species = list(species or sorted(EXT["species"]))
    items = list(items or FIT_GRID_ITEMS)
    label_w = 96
    header_h = 28
    footer_h = 18
    width = label_w + cell * len(items)
    height = header_h + cell * len(species) + footer_h
    sheet = Image.new("RGB", (width, height), (236, 232, 245))
    draw = ImageDraw.Draw(sheet)
    for col, (slot, iid) in enumerate(items):
        x = label_w + col * cell + 4
        draw.text((x, 8), f"{slot}: {iid}", fill=(40, 40, 60))
    for row, sp in enumerate(species):
        y = header_h + row * cell
        draw.text((6, y + cell // 2 - 6), sp, fill=(40, 40, 60))
        for col, (slot, iid) in enumerate(items):
            x = label_w + col * cell
            draw.rectangle((x, y, x + cell - 1, y + cell - 1), outline=(180, 174, 200))
            img = render_pet(sp, loadout={slot: iid}, native=False).resize(
                (cell, cell), Image.NEAREST
            )
            sheet.paste(img, (x, y), img)
    draw.text(
        (6, height - footer_h + 2),
        "launch-003 cosmetic fit grid v2 — anchors + per-species transforms",
        fill=(70, 66, 90),
    )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, optimize=True)
    return out


def contact_sheet(n=100, cols=10, cell=256, out=A / "contact_sheet_100_launch-003.png"):
    rows = (n + cols - 1) // cols; sheet = Image.new("RGB", (cols * cell, rows * (cell + 14)), (236, 232, 245)); d = ImageDraw.Draw(sheet); looks = []
    for i in range(n):
        lk = seeded_look(i); looks.append(lk); im = render_pet(**lk, native=True).resize((cell, cell), Image.NEAREST)
        x, y = (i % cols) * cell, (i // cols) * (cell + 14); sheet.paste(im, (x, y), im); d.text((x + 4, y + cell), f"#{i} {lk['species'][:5]} {lk['palette'][:6]}", fill=(40, 40, 60))
    sheet.save(out, optimize=True); return looks

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--fit-grid", action="store_true")
    ap.add_argument("--out", default=str(A / "preview" / "cosmetics_fit_grid_v2.png"))
    ap.add_argument("--cell", type=int, default=160)
    a = ap.parse_args()
    if a.fit_grid:
        path = render_fit_grid(a.out, cell=a.cell)
        print(f"wrote {path}")
    else:
        looks = contact_sheet(a.n); keys = {json.dumps([l["species"], l["palette"], l["marking"], l["loadout"]], sort_keys=True) for l in looks}
        print(f"rendered {len(looks)} looks, {len(keys)} distinct")
