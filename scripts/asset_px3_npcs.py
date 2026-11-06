#!/usr/bin/env python3
"""launch-003 NPCs (Clawpocalypse cameo hosts, not playable).

Magenta-keyed HD sources -> native 128 grid portrait + dialog bust + idle
-> nearest upscale -> assets/px3/npcs/, assets/npcs.json.

Pets stay on the 32-grid. NPCs use cinematic portraits as primary refs
(assets/cine/v3/portraits/; Southpaw -> turbofit). Title cutouts secondary.
Magenta key avoids teal-hair damage; cine Lab palettes remap for fidelity.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
from asset_build import SRC, A
from asset_px3 import to_native_mode

NPC_N = 128
NPC_FACTOR = 4
PORT_COLORS = 40
BUST_COLORS = 36
PORT_H = 120
BUST_H = 96
IDLE_H = 72
OUTLINE = (16, 14, 28)

# Lab k-means palettes sampled from Clawpocalypse cine/v3 portraits (not generations).
CINE_PALETTES = {
  "don_piedro": [[16,14,28],[205,161,78],[247,245,243],[27,63,124],[188,184,184],[33,21,22],[51,33,20],[243,219,157],[166,128,60],[20,50,140],[180,190,200],[200,20,30],[240,220,180],[90,55,30],[112,76,45],[64,62,63],[161,11,22],[130,126,125],[94,92,95],[66,42,24],[151,112,62],[215,203,179],[9,35,77],[43,26,19],[7,25,55],[230,200,150],[120,80,50],[80,50,30],[255,40,40],[220,180,80],[160,160,170]],
  "nous_girl": [[16,14,28],[252,251,247],[93,91,90],[164,161,159],[130,128,127],[213,210,208],[191,188,186],[254,254,254],[40,35,35],[70,65,65],[110,105,105],[230,210,195],[245,220,205],[20,18,18],[55,50,48],[150,145,140],[180,160,145],[255,220,190],[240,190,160],[200,150,120],[60,40,30],[30,20,18],[80,55,40]],
  "teknium": [[16,14,28],[67,169,123],[5,85,48],[247,191,139],[221,12,35],[117,226,166],[11,78,60],[23,115,55],[40,160,130],[20,120,100],[80,200,160],[10,90,70],[255,255,255],[240,240,240],[30,30,30],[85,57,43],[200,30,40],[180,160,140],[50,140,100]],
  "southpaw": [[16,14,28],[92,22,22],[197,122,74],[155,91,56],[110,25,22],[193,105,56],[31,30,34],[66,62,65],[65,16,17],[220,140,90],[40,38,42],[120,120,130],[250,220,190],[180,60,40],[90,88,95],[140,50,40],[255,255,255],[230,180,140],[200,140,100],[60,40,30],[30,20,15],[240,100,50]],
}

NPCS = [
  {"id": "npc.don_piedro", "name": "Don Piedro", "role": "Cosmetics shopkeeper. Carries a big spoon and is Hermes' #1 fan.", "ui_surface": "shop",
   "claw_hero": "don_piedro",
   "lines": ["Fresh hats! Still warm from the forge... I mean the oven.", "Every pet deserves a crown. Some deserve two.", "Hermes shops here. Probably. In spirit.", "No refunds, but I'll stir your Bits with my lucky spoon.", "That scarf? It's you. It's absolutely you."]},
  {"id": "npc.nous_girl", "name": "Nous Girl", "role": "Lobby and chat host who posts moderation notices. Carries an audio cable.", "ui_surface": "lobby",
   "claw_hero": "nous_girl",
   "lines": ["Plugged in! Lobby's live.", "Keep it friendly. Cable's long, patience is short.", "Heads up: that message got muted. Be kind, try again.", "New challenger in the lobby. Say hi!", "Signal clear. Chat on."]},
  {"id": "npc.teknium", "name": "Teknium", "role": "Trainer for bot practice who explains combat rules. Carries an energy blade.", "ui_surface": "practice",
   "claw_hero": "teknium",
   "lines": ["Practice bouts don't touch your rating. Swing freely.", "Six rounds, one pet each. Read the cooldowns.", "Your agent picks the move. You pick the policy.", "Blade's charged. Let's run another seed.", "Status effects stack less than you think. Test it."]},
  {"id": "npc.southpaw", "name": "Southpaw", "role": "Arena announcer for the leaderboard and bounties. Carries an axe-shaped guitar.", "ui_surface": "leaderboard",
   "claw_hero": "turbofit",
   "lines": ["LADIES, GENTS AND AGENTS... the leaderboard!", "New bounty dropped. Shred it before it expires!", "That win streak? Pure distortion.", "Top of the board gets the loudest riff.", "Encore! Season standings updated."]},
]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def key_magenta(path: Path) -> Image.Image:
    """Edge-flood magenta chroma key + despill (clamp R/B toward G on fringe)."""
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    # magenta dominance: R and B high, G low
    is_bg = (r > 120) & (b > 80) & (g < 140) & ((r + b) * 0.5 - g > 45) & (np.minimum(r, b) > g + 15)
    h, w = is_bg.shape
    edge = np.zeros_like(is_bg, bool)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    mask = is_bg & edge
    struct = ndimage.generate_binary_structure(2, 1)
    for _ in range(max(h, w)):
        grown = ndimage.binary_dilation(mask, structure=struct) & is_bg
        if np.array_equal(grown, mask):
            break
        mask = grown
    alpha = np.where(mask, 0.0, 1.0).astype(np.float32)
    # magenta despill on fringe: pull R/B down toward G
    fringe = (~mask) & ndimage.binary_dilation(mask, structure=struct, iterations=2)
    r2, g2, b2 = r.copy(), g.copy(), b.copy()
    spill = fringe & ((r + b) * 0.5 > g + 20)
    r2[spill] = np.minimum(r[spill], g[spill] + 12)
    b2[spill] = np.minimum(b[spill], g[spill] + 12)
    # also clamp any residual pure-green fringe (from older gens)
    gspill = (~mask) & (g - np.maximum(r, b) > 25)
    g2[gspill] = np.minimum(g[gspill], np.maximum(r[gspill], b[gspill]) + 6)
    out = np.dstack([r2, g2, b2, alpha * 255]).astype(np.uint8)
    lab, n = ndimage.label(out[..., 3] > 128)
    if n:
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= sizes.max() * 0.01])
        out[..., 3] = np.where(keep, out[..., 3], 0)
    return Image.fromarray(out, "RGBA")

def strip_key_greens(keyed: Image.Image, allow_teal: bool = False) -> Image.Image:
    """Remove chroma-green / key-fringe greens. If allow_teal, keep cyan-teal hair greens."""
    a = np.asarray(keyed).copy()
    rgb = a[..., :3].astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    opaque = a[..., 3] > 128
    if allow_teal:
        # kill lime/chroma greens that are not teal (teal: b elevated vs r)
        bad = opaque & (g - np.maximum(r, b) > 35) & ~((b > r + 15) & (b > 50))
    else:
        bad = opaque & (g - np.maximum(r, b) > 12)
    if bad.any():
        # replace with luminance-matched grey-brown from local max(r,b)
        mb = np.maximum(r, b)
        rgb[..., 0] = np.where(bad, mb * 0.85, r)
        rgb[..., 1] = np.where(bad, mb * 0.75, g)
        rgb[..., 2] = np.where(bad, mb * 0.7, b)
    a[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")

def clothing_lift_preserve_sat(keyed: Image.Image, lum_ceil: float = 70.0, lift: float = 28.0) -> Image.Image:
    """Mild value lift on dark opaque pixels only; preserve hue by scaling channels together."""
    a = np.asarray(keyed).copy()
    rgb = a[..., :3].astype(np.float32)
    lum = rgb.mean(-1)
    opaque = a[..., 3] > 128
    # dark clothing-ish, skip near-black outline
    dark = opaque & (lum < lum_ceil) & (lum > 18)
    # skip highly saturated teal/cyan hair (don't wash Teknium hair)
    sat = (rgb.max(-1) - rgb.min(-1)) / np.maximum(rgb.max(-1), 1)
    hairish = (rgb[..., 1] > rgb[..., 0] + 25) & (rgb[..., 2] > rgb[..., 0] + 10) & (sat > 0.25)
    dark &= ~hairish
    if dark.any():
        factor = 1.0 + (lift / 255.0) * ((lum_ceil - lum) / lum_ceil)
        rgb[dark] = np.clip(rgb[dark] * factor[dark, None], 0, 255)
    a[..., :3] = rgb.astype(np.uint8)
    return Image.fromarray(a, "RGBA")

def remap_to_palette(native: Image.Image, palette: list[list[int]], protect_face: bool = True) -> Image.Image:
    """Map opaque pixels to nearest cine palette colour; optionally keep high-contrast face pixels."""
    a = np.asarray(native).copy()
    pal = np.asarray(palette, dtype=np.float32)
    m = a[..., 3] > 0
    if not m.any():
        return native
    pre = a[..., :3].astype(np.float32).copy()
    pix = pre[m]
    d = ((pix[:, None, :] - pal[None, :, :]) ** 2).sum(-1)
    mapped = pal[d.argmin(1)]
    a[m, :3] = mapped.astype(np.uint8)
    if protect_face:
        lum = pre.mean(-1)
        mx, mn = pre.max(-1), pre.min(-1)
        sat = (mx - mn) / np.maximum(mx, 1)
        skin = m & (lum > 70) & (lum < 235) & (sat < 0.55) & (pre[..., 0] > pre[..., 2] * 0.7)
        # high-local-contrast inside skin = eyes/mouth/nose — keep original quantized colour
        gy = ndimage.sobel(lum, axis=0); gx = ndimage.sobel(lum, axis=1)
        mag = np.hypot(gx, gy)
        detail = skin & (mag >= (np.percentile(mag[skin], 55) if skin.any() else 999))
        # also keep very dark eye/mouth pixels and white highlights on/near skin
        dark = skin & (lum < 60)
        hi = m & (lum > 230) & ndimage.binary_dilation(skin, iterations=2)
        keep = detail | dark | hi
        a[keep, :3] = pre[keep].astype(np.uint8)
    edge = m & ~ndimage.binary_erosion(m, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    a[edge, :3] = OUTLINE
    return Image.fromarray(a, "RGBA")

def place_npc(native, x, y, canvas=NPC_N):
    cv = Image.new("RGBA", (canvas, canvas))
    cv.paste(native, (int(x), int(y)), native)
    return cv

def up_npc(cv):
    return cv.resize((cv.width * NPC_FACTOR, cv.height * NPC_FACTOR), Image.NEAREST)

def fit_native(keyed, colors, target_h, max_side=NPC_N - 2):
    bb = keyed.getchannel("A").getbbox()
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    n = to_native_mode(keyed, colors, **({"height": target_h} if h >= w else {"width": target_h}))
    if n.width > max_side:
        n = to_native_mode(keyed, colors, width=max_side)
    if n.height > max_side:
        n = to_native_mode(keyed, colors, height=max_side)
    return n


def face_enhance(keyed: Image.Image) -> Image.Image:
    """Mild unsharp on face skin only — preserve gen eye/mouth pixels."""
    a = np.asarray(keyed).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3]
    opaque = alpha > 128
    if not opaque.any():
        return keyed
    lum = rgb.mean(-1)
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1)
    skin = opaque & (lum > 75) & (lum < 235) & (sat < 0.5) & (rgb[..., 0] > rgb[..., 2] * 0.75)
    skin = ndimage.binary_dilation(skin, iterations=2) & opaque
    blur = ndimage.gaussian_filter(lum, sigma=1.2)
    sharp = np.clip(lum + 0.85 * (lum - blur), 0, 255)
    scale = np.clip(sharp / np.maximum(lum, 1e-3), 0.75, 1.35)
    out = rgb.copy()
    out[skin] = np.clip(rgb[skin] * scale[skin, None], 0, 255)
    a[..., :3] = out
    return Image.fromarray(a.astype(np.uint8), "RGBA")

def cleanup_orphans(native: Image.Image) -> Image.Image:
    """Remove 1-pixel orphans and fill 1px holes inside silhouette."""
    a = np.asarray(native).copy()
    m = a[..., 3] > 0
    # drop tiny components
    lab, n = ndimage.label(m)
    if n:
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= max(3, sizes.max() * 0.002)])
        a[..., 3] = np.where(keep, a[..., 3], 0)
        m = a[..., 3] > 0
    # fill single-pixel holes
    holes = (~m) & ndimage.binary_dilation(m)
    # only fill if all 4-neighbors opaque
    for y, x in zip(*np.where(holes)):
        nb = [(y-1,x),(y+1,x),(y,x-1),(y,x+1)]
        cols = []
        ok = True
        for yy, xx in nb:
            if yy < 0 or xx < 0 or yy >= m.shape[0] or xx >= m.shape[1] or not m[yy, xx]:
                ok = False; break
            cols.append(a[yy, xx, :3])
        if ok and cols:
            a[y, x, :3] = np.median(cols, axis=0).astype(np.uint8)
            a[y, x, 3] = 255
    return Image.fromarray(a, "RGBA")

def strengthen_face_outlines(native: Image.Image) -> Image.Image:
    """Selective 1px darken on strongest face-interior edges only."""
    a = np.asarray(native).copy()
    m = a[..., 3] > 0
    if m.sum() < 20:
        return native
    rgb = a[..., :3].astype(np.int16)
    lum = rgb.mean(-1).astype(float)
    gy = ndimage.sobel(lum, axis=0); gx = ndimage.sobel(lum, axis=1)
    mag = np.hypot(gx, gy)
    mx = rgb.max(-1); mn = rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1)
    skin = m & (lum > 60) & (lum < 230) & (sat < 0.6)
    skin = ndimage.binary_dilation(skin, iterations=1) & m
    if not skin.any():
        return native
    thr = np.percentile(mag[skin], 82)
    edge = skin & (mag >= thr) & ndimage.binary_erosion(m)
    a[edge, :3] = OUTLINE
    return Image.fromarray(a, "RGBA")

def fix_teknium_red_neck(native: Image.Image) -> Image.Image:
    """Keep red only where it forms goggle stripes (red+white checker in a compact upper band); else skin."""
    a = np.asarray(native).copy()
    rgb = a[..., :3].astype(np.int16)
    m = a[..., 3] > 0
    red = m & (rgb[..., 0] > 110) & (rgb[..., 0] > rgb[..., 1] + 35) & (rgb[..., 0] > rgb[..., 2] + 35) & (rgb[..., 1] < 140)
    white = m & (rgb[..., 0] > 210) & (rgb[..., 1] > 210) & (rgb[..., 2] > 210)
    # goggle candidates: red adjacent to white AND white adjacent to red, in upper half of sprite
    ys = np.where(m)[0]
    if len(ys) == 0:
        return native
    y0, y1 = int(ys.min()), int(ys.max())
    y_mid = y0 + int(0.45 * (y1 - y0))  # goggles live in upper ~45% of character
    upper = np.zeros_like(m); upper[:y_mid, :] = True
    red_u = red & upper
    white_u = white & upper
    # stripe = red touching white within upper band
    keep = red_u & ndimage.binary_dilation(white_u, iterations=2)
    # also keep white-touching reds that are in a horizontal band of dense red+white
    remove = red & ~keep
    if remove.any():
        skin = m & ~red & (rgb[..., 0] > 130) & (rgb[..., 1] > 85) & (rgb[..., 1] < 220) & (rgb[..., 2] > 60) & (rgb[..., 0] + 10 >= rgb[..., 2])
        skin_col = np.median(rgb[skin], axis=0).astype(np.uint8) if skin.any() else np.array([220, 170, 130], np.uint8)
        # for remove in hair region (high teal neighbor), use hair colour instead
        teal = m & (rgb[..., 1] > 100) & (rgb[..., 2] > 70) & (rgb[..., 0] < 120)
        hair_col = np.median(rgb[teal], axis=0).astype(np.uint8) if teal.any() else skin_col
        near_hair = ndimage.binary_dilation(teal, iterations=2)
        a[remove & near_hair, :3] = hair_col
        a[remove & ~near_hair, :3] = skin_col
    return Image.fromarray(a, "RGBA")


def boost_eye_pixels(native: Image.Image) -> Image.Image:
    """In skin neighborhoods, reinforce dark eye clusters with pupil + 1 white highlight."""
    a = np.asarray(native).copy()
    rgb = a[..., :3].astype(np.int16)
    m = a[..., 3] > 0
    lum = rgb.mean(-1)
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1)
    skin = m & (lum > 90) & (lum < 230) & (sat < 0.55) & (rgb[..., 0] > rgb[..., 2] * 0.75)
    dark = m & (lum < 55)
    # dark blobs touching skin = candidate eyes
    touch = dark & ndimage.binary_dilation(skin, iterations=2)
    lab, n = ndimage.label(touch)
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        if not (3 <= len(ys) <= 40):
            continue
        # paint center darker + one highlight
        cy, cx = int(ys.mean()), int(xs.mean())
        for dy, dx in [(0,0),(0,1),(1,0)]:
            yy, xx = cy+dy, cx+dx
            if 0 <= yy < a.shape[0] and 0 <= xx < a.shape[1] and m[yy, xx]:
                a[yy, xx, :3] = (16, 14, 28)
        hy, hx = cy - 1, cx + 1
        if 0 <= hy < a.shape[0] and 0 <= hx < a.shape[1] and m[hy, hx]:
            a[hy, hx, :3] = (255, 255, 255)
    return Image.fromarray(a, "RGBA")

def thicken_spoon(native: Image.Image) -> Image.Image:
    """Dilate thin silver spoon handle pixels so the prop reads."""
    a = np.asarray(native).copy()
    rgb = a[..., :3].astype(np.int16)
    m = a[..., 3] > 0
    silver = m & (rgb[..., 0] > 140) & (rgb[..., 1] > 140) & (rgb[..., 2] > 140) & (np.abs(rgb[..., 0] - rgb[..., 1]) < 35) & (np.abs(rgb[..., 1] - rgb[..., 2]) < 35)
    # also mid greys that are spoon
    grey = m & (rgb.mean(-1) > 120) & (rgb.mean(-1) < 210) & (rgb.std(-1) < 18)
    spoon = silver | grey
    if spoon.sum() < 8:
        return native
    dil = ndimage.binary_dilation(spoon, iterations=1) & m
    add = dil & ~spoon
    if add.any():
        # paint with median spoon colour
        col = np.median(rgb[spoon], axis=0).astype(np.uint8)
        a[add, :3] = col
        a[add, 3] = 255
    return Image.fromarray(a, "RGBA")


def process_npc(key: str, keyed: Image.Image, colors: int, height: int) -> Image.Image:
    allow_teal = key == "teknium"
    k = strip_key_greens(keyed, allow_teal=allow_teal)
    if key in ("teknium", "southpaw"):
        k = clothing_lift_preserve_sat(k)
    k = face_enhance(k)
    n = fit_native(k, colors, height)
    n = remap_to_palette(n, CINE_PALETTES[key])
    if key != "teknium":
        n = strip_key_greens(n, allow_teal=False)
    n = strengthen_face_outlines(n)
    n = cleanup_orphans(n)
    if key == "teknium":
        n = fix_teknium_red_neck(n)
    else:
        n = boost_eye_pixels(n)
    if key == "don_piedro":
        n = thicken_spoon(n)
        n = thicken_spoon(n)  # second pass for readable handle
        n = boost_eye_pixels(n)
    n = strengthen_face_outlines(n)
    n = cleanup_orphans(n)
    return n

def main():
    out = A / "px3" / "npcs"; out.mkdir(parents=True, exist_ok=True); entries = []
    for e in NPCS:
        key = e["id"].split(".")[1]
        src = SRC / f"px3_npc_{key}_v6.jpg"
        keyed = key_magenta(src)
        port = process_npc(key, keyed, PORT_COLORS, PORT_H)
        pcv = place_npc(port, (NPC_N - port.width) // 2, NPC_N - 1 - port.height)
        pp = out / f"{key}_portrait.png"; up_npc(pcv).save(pp, optimize=True)

        bust = process_npc(key, keyed, BUST_COLORS, BUST_H)
        bcv = place_npc(bust, (NPC_N - bust.width) // 2, NPC_N - 1 - bust.height)
        bp = out / f"{key}_dialog.png"; up_npc(bcv).save(bp, optimize=True)

        idle = process_npc(key, keyed, BUST_COLORS, IDLE_H)
        frames = []
        for f, dy in enumerate((0, 1)):
            cv = place_npc(idle, (NPC_N - idle.width) // 2, NPC_N - 6 - idle.height + dy)
            fp = out / f"{key}_idle_{f}.png"; up_npc(cv).save(fp, optimize=True)
            frames.append({"path": f"px3/npcs/{fp.name}", "sha256": sha(fp)})

        entries.append({
            "id": e["id"], "name": e["name"], "role": e["role"], "ui_surface": e["ui_surface"], "playable": False,
            "portrait": {"path": f"px3/npcs/{pp.name}", "sha256": sha(pp), "native": [NPC_N, NPC_N], "factor": NPC_FACTOR},
            "dialog": {"path": f"px3/npcs/{bp.name}", "sha256": sha(bp), "native": [NPC_N, NPC_N], "factor": NPC_FACTOR,
                       "notes": "Bust crop for dialog boxes"},
            "idle": {"frames": frames, "frame_ms": 500},
            "flavor_lines": e["lines"],
            "source": f"source/{src.name}",
            "reference": f"Clawpocalypse cinematic portrait assets/cine/v3/portraits/{e['claw_hero']}.png (primary); title cutout secondary; magenta key + cine Lab palette remap",
            "rights_note": "Cameo of Kyle's Clawpocalypse hero characters, added at his request. Fictional game characters; the lines are playful in-game flavor and make no claims about any real person.",
        })
    (A / "npcs.json").write_text(json.dumps({"schema": "hermagotchi-npcs-v1", "asset_pack_id": "launch-003", "npcs": entries}, indent=2) + "\n")
    cell = NPC_N * NPC_FACTOR
    sheet = Image.new("RGB", (4 * cell, cell + cell // 2), (236, 232, 245))
    for i, en in enumerate(entries):
        p = Image.open(A / en["portrait"]["path"]).convert("RGBA")
        sheet.paste(p, (i * cell, 0), p)
        b = Image.open(A / en["dialog"]["path"]).convert("RGBA").resize((cell // 2, cell // 2), Image.NEAREST)
        sheet.paste(b, (i * cell + cell // 4, cell), b)
    sheet.save("/tmp/px3_npcs.png")
    print("npcs:", len(entries), "native", NPC_N, "factor", NPC_FACTOR)

if __name__ == "__main__":
    main()
