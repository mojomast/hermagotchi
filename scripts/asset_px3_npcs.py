#!/usr/bin/env python3
"""launch-003 NPCs — hand-pixel portraits (not painterly Lab remap).

Sources: GenerateImage TRUE pixel-art bust prompts (v7), then:
  key flat grey bg → snap to fixed 12–20 hand palette (from cine/v3 refs)
  → BOX resize onto native grid → binary alpha → fill holes
  → selective 1px outline → light face pixel pass → re-snap.
References: Clawpocalypse assets/cine/v3/portraits/ (Southpaw = turbofit).
Pets stay on 32-grid.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
from asset_build import SRC, A

NPC_N = 128
NPC_FACTOR = 4
OUTLINE = (16, 14, 28)
BG = (48, 48, 56)  # gen background ≈ #303038

# Hand-picked shade ramps from cine/v3 portraits (12–20 colours each).
PALETTES = {
  "don_piedro": [
    OUTLINE, (32, 19, 16), (63, 41, 24), (110, 74, 45), (140, 104, 44), (155, 114, 68),
    (207, 196, 176), (236, 231, 228), (209, 166, 86), (180, 140, 60),
    (27, 64, 124), (8, 32, 71), (40, 90, 160),
    (162, 12, 23), (220, 40, 40), (255, 80, 80),
    (161, 156, 156), (200, 200, 205), (255, 255, 255), (103, 101, 102),
  ],
  "nous_girl": [
    OUTLINE, (22, 19, 20), (46, 42, 43), (71, 68, 68), (96, 94, 93), (122, 120, 119),
    (151, 149, 147), (177, 174, 172), (215, 212, 210), (231, 229, 227), (254, 254, 253),
    (249, 242, 236), (240, 210, 190), (220, 180, 150), (200, 150, 120),
    (40, 30, 28), (80, 50, 40),
  ],
  "teknium": [
    OUTLINE, (22, 40, 23), (6, 86, 52), (6, 125, 91), (32, 148, 100), (80, 144, 62),
    (96, 163, 129), (118, 226, 166), (40, 180, 140), (20, 120, 100),
    (251, 204, 159), (247, 190, 138), (179, 118, 79), (220, 170, 130),
    (220, 10, 34), (255, 40, 50), (248, 247, 243), (255, 255, 255),
    (30, 30, 30), (60, 60, 60),
  ],
  "southpaw": [
    OUTLINE, (23, 23, 26), (41, 40, 44), (64, 60, 63), (90, 88, 95), (120, 120, 130),
    (40, 8, 7), (65, 14, 13), (89, 23, 22), (112, 26, 22), (135, 45, 29),
    (165, 48, 27), (188, 61, 28), (193, 106, 58), (236, 152, 89),
    (226, 212, 198), (240, 190, 150), (200, 140, 100), (255, 255, 255), (180, 180, 190),
  ],
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

def key_flat_bg(path: Path, bg=BG, tol=38) -> Image.Image:
    """Key near-flat grey background (edge flood only).

    Do NOT key low-luma pixels — black bob / black vest would vanish.
    Only pixels chromatically near the flat grey gen bg, grown from edges.
    """
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    dist = np.linalg.norm(im - np.array(bg, dtype=np.float32), axis=-1)
    # true flat grey: low chroma AND near bg
    chroma = im.max(-1) - im.min(-1)
    is_bg = (dist < tol) & (chroma < 28)
    h, w = is_bg.shape
    edge = np.zeros_like(is_bg, bool)
    edge[0] = edge[-1] = edge[:, 0] = edge[:, -1] = True
    mask = is_bg & edge
    struct = ndimage.generate_binary_structure(2, 1)
    for _ in range(max(h, w)):
        grown = ndimage.binary_dilation(mask, structure=struct) & is_bg
        if np.array_equal(grown, mask):
            break
        mask = grown
    alpha = np.where(mask, 0, 255).astype(np.uint8)
    lab, n = ndimage.label(alpha > 128)
    if n:
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= sizes.max() * 0.02])
        alpha = np.where(keep, alpha, 0).astype(np.uint8)
    return Image.fromarray(np.dstack([im.astype(np.uint8), alpha]), "RGBA")

def snap_palette(im: Image.Image, palette: list) -> Image.Image:
    a = np.asarray(im).copy()
    pal = np.asarray(palette, dtype=np.float32)
    m = a[..., 3] > 128
    if not m.any():
        return im
    pix = a[m, :3].astype(np.float32)
    d = ((pix[:, None, :] - pal[None, :, :]) ** 2).sum(-1)
    a[m, :3] = pal[d.argmin(1)].astype(np.uint8)
    a[..., 3] = np.where(m, 255, 0).astype(np.uint8)
    return Image.fromarray(a, "RGBA")

def fill_internal_holes(native: Image.Image) -> Image.Image:
    a = np.asarray(native).copy()
    m = a[..., 3] > 0
    inv = ~m
    lab, _ = ndimage.label(inv)
    border = set(lab[0].tolist()) | set(lab[-1].tolist()) | set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
    holes = inv & ~np.isin(lab, list(border | {0}))
    if holes.any():
        ys, xs = np.where(m)
        for y, x in zip(*np.where(holes)):
            j = int(np.argmin((ys - y) ** 2 + (xs - x) ** 2))
            a[y, x, :3] = a[ys[j], xs[j], :3]
            a[y, x, 3] = 255
    return Image.fromarray(a, "RGBA")

def reconnect(native: Image.Image, iters: int = 1) -> Image.Image:
    a = np.asarray(native).copy()
    m = a[..., 3] > 0
    closed = ndimage.binary_closing(m, structure=np.ones((3, 3)), iterations=iters)
    add = closed & ~m
    if add.any():
        ys, xs = np.where(m)
        for y, x in zip(*np.where(add)):
            j = int(np.argmin((ys - y) ** 2 + (xs - x) ** 2))
            a[y, x, :3] = a[ys[j], xs[j], :3]
            a[y, x, 3] = 255
    return Image.fromarray(a, "RGBA")

def cleanup_fringe(native: Image.Image) -> Image.Image:
    """Drop only tiny far-away speckles; keep headphones/spoon pieces near body."""
    a = np.asarray(native).copy()
    m = a[..., 3] > 0
    lab, n = ndimage.label(m)
    if n:
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        main = int(np.argmax(sizes)) + 1
        near = ndimage.binary_dilation(lab == main, iterations=4)
        keep_ids = [main]
        for i, s in enumerate(sizes, 1):
            if i == main:
                continue
            if s >= 12 or ((lab == i) & near).any():
                keep_ids.append(i)
        a[..., 3] = np.where(np.isin(lab, keep_ids), 255, 0).astype(np.uint8)
    return Image.fromarray(a, "RGBA")

def outline_silhouette(native: Image.Image) -> Image.Image:
    a = np.asarray(native).copy()
    m = a[..., 3] > 0
    edge = m & ~ndimage.binary_erosion(m, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    a[edge, :3] = OUTLINE
    return Image.fromarray(a, "RGBA")

def to_native_box(keyed: Image.Image, palette: list, height: int, max_w: int = NPC_N - 2) -> Image.Image:
    """Hand-palette snap → BOX onto native grid → binary alpha. Flat colours, no dither."""
    sn = snap_palette(keyed, palette)
    a0 = np.asarray(sn)
    m0 = a0[..., 3] > 128
    ys, xs = np.nonzero(m0)
    a0 = a0[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = a0.shape[:2]
    # Prefer target height; clamp width
    s = height / h
    tw, th = max(1, round(w * s)), max(1, round(h * s))
    if tw > max_w:
        s = max_w / w
        tw, th = max_w, max(1, round(h * s))
    if th > NPC_N - 1:
        s = (NPC_N - 1) / h
        tw, th = max(1, min(max_w, round(w * s))), NPC_N - 1
    rgb = Image.fromarray(a0[..., :3]).resize((tw, th), Image.BOX)
    al = Image.fromarray(a0[..., 3]).resize((tw, th), Image.BOX)
    out = np.dstack([np.asarray(rgb), np.where(np.asarray(al) > 120, 255, 0).astype(np.uint8)])
    return snap_palette(Image.fromarray(out, "RGBA"), palette)

def hand_face_pass(native: Image.Image, key: str) -> Image.Image:
    """Light native-grid face emphasis — reinforce, don't invent over good features."""
    a = np.asarray(native).copy()
    h, w = a.shape[:2]
    m = a[..., 3] > 0
    rgb = a[..., :3].astype(np.int16)
    lum = rgb.mean(-1)

    def setp(y, x, col):
        if 0 <= y < h and 0 <= x < w and m[y, x]:
            a[y, x, :3] = col

    ys, xs = np.where(m)
    if not len(ys):
        return native
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    fy0 = y0 + int(0.08 * (y1 - y0))
    fy1 = y0 + int(0.52 * (y1 - y0))
    fx0 = x0 + int(0.18 * (x1 - x0))
    fx1 = x0 + int(0.82 * (x1 - x0))

    if key == "nous_girl":
        face = m.copy(); face[:fy0] = False; face[fy1:] = False; face[:, :fx0] = False; face[:, fx1:] = False
        dark = face & (lum < 80) & (rgb[..., 0] < 100)
        lab, n = ndimage.label(dark)
        eyes = []
        for i in range(1, n + 1):
            yy, xx = np.where(lab == i)
            if 2 <= len(yy) <= 40:
                eyes.append((int(yy.mean()), int(xx.mean()), len(yy)))
        for cy, cx, _ in sorted(eyes, key=lambda e: -e[2])[:2]:
            for dy in range(-1, 2):
                for dx in range(-2, 3):
                    setp(cy + dy, cx + dx, OUTLINE)
            setp(cy, cx, (22, 19, 20))
            setp(cy - 1, cx + 1, (254, 254, 253))
        my = fy0 + int(0.72 * (fy1 - fy0))
        mx = (fx0 + fx1) // 2
        for dx in range(-2, 3):
            setp(my, mx + dx, (80, 50, 40))

    if key == "southpaw":
        # Only reinforce grin if teeth already present; else draw modest smile
        face = m.copy(); face[:fy0] = False; face[fy1:] = False; face[:, :fx0] = False; face[:, fx1:] = False
        white = face & (rgb.min(-1) > 220)
        if white.sum() < 8:
            my = fy0 + int(0.70 * (fy1 - fy0))
            mx = (fx0 + fx1) // 2
            for dx in range(-5, 6):
                setp(my, mx + dx, (255, 255, 255))
                setp(my - 1, mx + dx, OUTLINE)
                setp(my + 1, mx + dx, OUTLINE)
        # brows / eyes if missing dark clusters
        dark = face & (lum < 55)
        if dark.sum() < 10:
            mx = (fx0 + fx1) // 2
            cy = fy0 + int(0.38 * (fy1 - fy0))
            for cx in (mx - 7, mx + 5):
                for dy in range(-1, 2):
                    for dx in range(-2, 3):
                        setp(cy + dy, cx + dx, OUTLINE)
                setp(cy - 1, cx + 1, (255, 255, 255))
                for dx in range(-3, 4):
                    setp(cy - 3, cx + dx, OUTLINE)

    if key == "don_piedro":
        face = m.copy(); face[:fy0] = False; face[fy1:] = False
        red = face & (rgb[..., 0] > 140) & (rgb[..., 0] > rgb[..., 1] + 40)
        if red.any():
            cy, cx = int(np.where(red)[0].mean()), int(np.where(red)[1].mean())
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    if dy * dy + dx * dx <= 5:
                        setp(cy + dy, cx + dx, (162, 12, 23))
            setp(cy - 1, cx - 1, (255, 255, 255))
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    if 6 <= dy * dy + dx * dx <= 10:
                        setp(cy + dy, cx + dx, (209, 166, 86))
        # thicken spoon (silver)
        silver = m & (rgb[..., 0] > 150) & (rgb[..., 1] > 150) & (rgb[..., 2] > 145) & (np.abs(rgb[..., 0].astype(int) - rgb[..., 1]) < 35)
        if silver.any():
            dil = ndimage.binary_dilation(silver, iterations=2)
            col = np.median(rgb[silver], axis=0).astype(np.uint8)
            # allow 1px growth past current silhouette for spoon weight
            a[dil, :3] = col
            a[dil, 3] = 255
            m = a[..., 3] > 0

    if key == "teknium":
        # mouth on lower face: ~58% down the full sprite bbox
        my = y0 + int(0.48 * (y1 - y0))
        mx = (x0 + x1) // 2 + 3
        for dx in range(-5, 6):
            setp(my, mx + dx, OUTLINE)
        setp(my, mx + 4, (179, 118, 79))
        setp(my - 1, mx + 4, (247, 190, 138))
        # scrub stray red below visor band
        red = m & (rgb[..., 0] > 140) & (rgb[..., 0] > rgb[..., 1] + 40) & (rgb[..., 1] < 120)
        white = m & (rgb.min(-1) > 200)
        y_mid = y0 + int(0.40 * (y1 - y0))
        bad = red & (np.arange(h)[:, None] >= y_mid) & ~ndimage.binary_dilation(white, iterations=2)
        skin = m & (rgb[..., 0] > 180) & (rgb[..., 1] > 120) & (rgb[..., 2] > 90)
        if bad.any() and skin.any():
            a[bad, :3] = np.median(rgb[skin], axis=0).astype(np.uint8)

    return Image.fromarray(a, "RGBA")

def scrub_thin_artifacts(native: Image.Image, key: str) -> Image.Image:
    """Remove 1px white/grey streak glitches that aren't teeth or studs."""
    a = np.asarray(native).copy()
    h, w = a.shape[:2]
    m = a[..., 3] > 0
    rgb = a[..., :3].astype(np.int16)
    white = m & (rgb.min(-1) > 210)
    lab, n = ndimage.label(white)
    ys_all, xs_all = np.where(m)
    y0, y1 = (int(ys_all.min()), int(ys_all.max())) if len(ys_all) else (0, h)
    # estimated mouth band
    mouth_y0 = y0 + int(0.45 * (y1 - y0))
    mouth_y1 = y0 + int(0.72 * (y1 - y0))
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        hh = int(ys.max() - ys.min() + 1)
        ww = int(xs.max() - xs.min() + 1)
        cy = int(ys.mean())
        # thin horizontal streak not in mouth band, or tiny streak
        if hh <= 2 and ww >= 6:
            in_mouth = mouth_y0 <= cy <= mouth_y1 and key in ("southpaw",)
            if not in_mouth or ww > 14:
                # recolour from nearest non-white opaque
                for y, x in zip(ys, xs):
                    # sample neighbors
                    cols = []
                    for dy, dx in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1)):
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < h and 0 <= xx < w and m[yy, xx] and not white[yy, xx]:
                            cols.append(a[yy, xx, :3])
                    if cols:
                        a[y, x, :3] = np.median(cols, axis=0).astype(np.uint8)
    # drop tiny fringe components (<10) far from main
    m = a[..., 3] > 0
    lab, n = ndimage.label(m)
    if n:
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        main = int(np.argmax(sizes)) + 1
        near = ndimage.binary_dilation(lab == main, iterations=2)
        keep = np.zeros_like(m)
        keep[lab == main] = True
        for i, s in enumerate(sizes, 1):
            if i == main:
                continue
            if s >= 16 and ((lab == i) & near).any():
                keep[lab == i] = True
            elif s >= 8 and ((lab == i) & near).any() and s >= 12:
                keep[lab == i] = True
        # keep near mid-size pieces only if touching dilated main
        for i, s in enumerate(sizes, 1):
            if i == main:
                continue
            if ((lab == i) & near).any() and s >= 5:
                keep[lab == i] = True
        a[..., 3] = np.where(keep, 255, 0).astype(np.uint8)
    return Image.fromarray(a, "RGBA")

def drop_loose_pixels(native: Image.Image) -> Image.Image:
    """Kill isolated / single-neighbor fringe pixels (not thin props)."""
    a = np.asarray(native).copy()
    m = a[..., 3] > 0
    kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], int)
    nbrs = ndimage.convolve(m.astype(int), kernel, mode="constant", cval=0)
    rgb = a[..., :3].astype(int)
    # protect silver/spoon-ish and pure white studs/teeth
    protect = ((rgb.min(-1) > 150) & (np.abs(rgb[..., 0] - rgb[..., 1]) < 40)) | (rgb.min(-1) > 230)
    drop = m & (nbrs <= 1) & ~protect
    a[drop, 3] = 0
    # also drop 2-neighbor speckles that are light-on-dark fringe outside bbox core
    drop2 = m & (nbrs == 2) & (rgb.mean(-1) > 180) & ~protect
    # only if near transparent
    near_t = ndimage.binary_dilation(~m, iterations=1)
    a[drop2 & near_t, 3] = 0
    return Image.fromarray(a, "RGBA")

def place(native, x, y):

    cv = Image.new("RGBA", (NPC_N, NPC_N))
    cv.paste(native, (int(x), int(y)), native)
    return cv

def up(cv):
    return cv.resize((cv.width * NPC_FACTOR, cv.height * NPC_FACTOR), Image.NEAREST)

def finish(n: Image.Image, key: str, pal: list) -> Image.Image:
    n = fill_internal_holes(n)
    n = reconnect(n, iters=1)
    n = cleanup_fringe(n)
    n = drop_loose_pixels(n)
    n = outline_silhouette(n)
    n = hand_face_pass(n, key)
    n = scrub_thin_artifacts(n, key)
    n = snap_palette(n, pal)
    n = fill_internal_holes(n)
    n = cleanup_fringe(n)
    n = drop_loose_pixels(n)
    n = scrub_thin_artifacts(n, key)
    n = outline_silhouette(n)
    return n

def build_one(key: str):
    pal = PALETTES[key]
    keyed = key_flat_bg(SRC / f"px3_npc_{key}_v7.jpg")
    port = finish(to_native_box(keyed, pal, height=118), key, pal)
    bust = finish(to_native_box(keyed, pal, height=96), key, pal)
    idle = finish(to_native_box(keyed, pal, height=72), key, pal)
    return port, bust, idle

def main():
    out = A / "px3" / "npcs"; out.mkdir(parents=True, exist_ok=True)
    old = {}
    if (A / "npcs.json").exists():
        old = {n["id"]: n for n in json.loads((A / "npcs.json").read_text())["npcs"]}
    entries = []
    for e in NPCS:
        key = e["id"].split(".")[1]
        port, bust, idle = build_one(key)
        pp = out / f"{key}_portrait.png"
        up(place(port, (NPC_N - port.width) // 2, NPC_N - 1 - port.height)).save(pp, optimize=True)
        bp = out / f"{key}_dialog.png"
        up(place(bust, (NPC_N - bust.width) // 2, NPC_N - 1 - bust.height)).save(bp, optimize=True)
        frames = []
        for f, dy in enumerate((0, 1)):
            fp = out / f"{key}_idle_{f}.png"
            up(place(idle, (NPC_N - idle.width) // 2, NPC_N - 6 - idle.height + dy)).save(fp, optimize=True)
            frames.append({"path": f"px3/npcs/{fp.name}", "sha256": sha(fp)})
        flavor = old.get(e["id"], {}).get("flavor_lines", e["lines"])
        entries.append({
            "id": e["id"], "name": e["name"], "role": e["role"], "ui_surface": e["ui_surface"], "playable": False,
            "portrait": {"path": f"px3/npcs/{pp.name}", "sha256": sha(pp), "native": [NPC_N, NPC_N], "factor": NPC_FACTOR},
            "dialog": {"path": f"px3/npcs/{bp.name}", "sha256": sha(bp), "native": [NPC_N, NPC_N], "factor": NPC_FACTOR,
                       "notes": "Bust crop for dialog boxes"},
            "idle": {"frames": frames, "frame_ms": 500},
            "flavor_lines": flavor,
            "source": f"source/px3_npc_{key}_v7.jpg",
            "reference": (
                f"Clawpocalypse cinematic portrait assets/cine/v3/portraits/{e['claw_hero']}.png — "
                "hand-pixel: GenerateImage SNES bust + fixed hand palette snap + BOX native grid + "
                "1px outline + face pixel pass (not painterly Lab remap)"
            ),
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
    print("npcs:", len(entries), "hand-pixel native", NPC_N)

if __name__ == "__main__":
    main()
