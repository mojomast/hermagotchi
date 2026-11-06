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
    OUTLINE, (8, 8, 10), (23, 23, 26), (41, 40, 44), (64, 60, 63), (90, 88, 95), (120, 120, 130),
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


def smooth_silhouette(native: Image.Image) -> Image.Image:
    """Remove 1px bumps / fill 1px notches on the silhouette; keep props."""
    a = np.asarray(native).copy()
    m = a[..., 3] > 0
    # opening then closing with cross (gentle)
    struct = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
    opened = ndimage.binary_opening(m, structure=struct, iterations=1)
    # don't delete large chunks — only drop pixels that opening removed AND have <=2 nbrs
    ker = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], int)
    nbrs = ndimage.convolve(m.astype(int), ker, mode="constant", cval=0)
    drop = m & ~opened & (nbrs <= 3)
    a[drop, 3] = 0
    m = a[..., 3] > 0
    closed = ndimage.binary_closing(m, structure=struct, iterations=1)
    add = closed & ~m
    if add.any():
        ys, xs = np.where(m)
        for y, x in zip(*np.where(add)):
            j = int(np.argmin((ys - y) ** 2 + (xs - x) ** 2))
            a[y, x, :3] = a[ys[j], xs[j], :3]
            a[y, x, 3] = 255
    return Image.fromarray(a, "RGBA")

def scrub_fringe_hard(native: Image.Image) -> Image.Image:
    """Kill orphan / isolated fringe flecks on hair edges (Kyle cleanup)."""
    a = np.asarray(native).copy()
    for _ in range(3):
        m = a[..., 3] > 0
        ker = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], int)
        nbrs = ndimage.convolve(m.astype(int), ker, mode="constant", cval=0)
        # drop isolated and single-bridge tip pixels
        drop = m & (nbrs <= 2)
        a[drop, 3] = 0
        # drop tiny components
        m = a[..., 3] > 0
        lab, n = ndimage.label(m)
        if n:
            sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
            main = int(np.argmax(sizes)) + 1
            near = ndimage.binary_dilation(lab == main, iterations=1)
            keep = lab == main
            for i, s in enumerate(sizes, 1):
                if i == main:
                    continue
                # only keep substantial pieces touching main (headphones cups etc.)
                if s >= 20 and ((lab == i) & near).any():
                    keep |= lab == i
            a[..., 3] = np.where(keep, 255, 0).astype(np.uint8)
    return Image.fromarray(a, "RGBA")

def eye_highlights(native: Image.Image, key: str) -> Image.Image:
    """Ensure readable eyes with a clear highlight pixel (upper-left light)."""
    a = np.asarray(native).copy()
    h, w = a.shape[:2]
    m = a[..., 3] > 0
    rgb = a[..., :3].astype(np.int16)
    lum = rgb.mean(-1)
    ys, xs = np.where(m)
    if not len(ys):
        return native
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    fy0 = y0 + int(0.10 * (y1 - y0))
    fy1 = y0 + int(0.48 * (y1 - y0))
    fx0 = x0 + int(0.15 * (x1 - x0))
    fx1 = x0 + int(0.85 * (x1 - x0))
    face = m.copy(); face[:fy0] = False; face[fy1:] = False; face[:, :fx0] = False; face[:, fx1:] = False

    def setp(y, x, col):
        if 0 <= y < h and 0 <= x < w and a[y, x, 3] > 0:
            a[y, x, :3] = col

    if key == "teknium":
        return Image.fromarray(a, "RGBA")  # visor covers eyes

    if key == "don_piedro":
        # monocle already red; ensure glint + open-eye pupil highlight
        red = face & (rgb[..., 0] > 140) & (rgb[..., 0] > rgb[..., 1] + 40)
        if red.any():
            cy, cx = int(np.where(red)[0].mean()), int(np.where(red)[1].mean())
            setp(cy - 1, cx - 1, (255, 255, 255))
        dark = face & (lum < 55) & (rgb[..., 0] < 90)
        if dark.any():
            lab, n = ndimage.label(dark)
            best = None
            for i in range(1, n + 1):
                yy, xx = np.where(lab == i)
                if 2 <= len(yy) <= 30:
                    if best is None or len(yy) > best[2]:
                        best = (int(yy.mean()), int(xx.mean()), len(yy))
            if best:
                cy, cx, _ = best
                setp(cy, cx, OUTLINE)
                setp(cy - 1, cx + 1, (255, 255, 255))
        return Image.fromarray(a, "RGBA")

    # nous / southpaw: dark eye clusters
    dark = face & (lum < 70)
    lab, n = ndimage.label(dark)
    eyes = []
    for i in range(1, n + 1):
        yy, xx = np.where(lab == i)
        if 3 <= len(yy) <= 50:
            eyes.append((int(yy.mean()), int(xx.mean()), len(yy)))
    for cy, cx, _ in sorted(eyes, key=lambda e: -e[2])[:2]:
        setp(cy, cx, OUTLINE)
        setp(cy, cx + 1, (22, 19, 20) if key == "nous_girl" else (23, 23, 26))
        setp(cy - 1, cx + 1, (255, 255, 255))  # upper-right-of-pupil = light from upper-left on sphere
    return Image.fromarray(a, "RGBA")

def fix_don_spoon(native: Image.Image) -> Image.Image:
    """Thicker clearer spoon with metallic highlight (upper-left light)."""
    a = np.asarray(native).copy()
    h, w = a.shape[:2]
    m = a[..., 3] > 0
    rgb = a[..., :3].astype(np.int16)
    ys, xs = np.where(m)
    if not len(ys):
        return native
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    # spoon lives on the RIGHT half, mid-upper: diagonal silver not part of bulky armour mass
    # armour = large white block; spoon = elongated thin silver
    cand = m & (rgb[..., 0] > 145) & (rgb[..., 1] > 145) & (rgb[..., 2] > 140)
    cand &= (np.abs(rgb[..., 0].astype(int) - rgb[..., 1]) < 45)
    cand &= (np.arange(w)[None, :] > (x0 + x1) // 2 - 5)  # rightish
    # exclude very bottom (chest armour)
    cand &= (np.arange(h)[:, None] < y0 + int(0.72 * (y1 - y0)))
    if cand.sum() < 8:
        # fallback: any mid-grey thin structure on right of face
        cand = m & (rgb.mean(-1) > 150) & (rgb.mean(-1) < 230)
        cand &= (np.arange(w)[None, :] > (x0 + x1) // 2)
        cand &= (np.arange(h)[:, None] < y0 + int(0.65 * (y1 - y0)))
        cand &= (np.arange(h)[:, None] > y0 + int(0.15 * (y1 - y0)))
    if not cand.any():
        return native
    # keep largest elongated component
    lab, n = ndimage.label(cand)
    best_i, best_score = None, -1
    for i in range(1, n + 1):
        yy, xx = np.where(lab == i)
        if len(yy) < 6:
            continue
        hh = yy.max() - yy.min() + 1
        ww = xx.max() - xx.min() + 1
        score = len(yy) * (max(hh, ww) / max(1, min(hh, ww)))  # prefer elongated
        if score > best_score:
            best_score, best_i = score, i
    if best_i is None:
        return native
    spoon = lab == best_i
    sy, sx = np.where(spoon)
    # fit diagonal axis (rightward-up typical)
    # thicken heavily along normal to the spoon axis
    thick = ndimage.binary_dilation(spoon, structure=np.ones((3, 3)), iterations=3)
    # extend tip toward upper-right
    tip_y, tip_x = int(sy[np.argmax(sx)]), int(sx.max())
    for t in range(1, 5):
        yy, xx = tip_y - t // 2, tip_x + t
        if 0 <= yy < h and 0 <= xx < w:
            for dy in range(-2, 3):
                for dx in range(-1, 2):
                    y2, x2 = yy + dy, xx + dx
                    if 0 <= y2 < h and 0 <= x2 < w:
                        thick[y2, x2] = True
    metal = (161, 156, 156)
    hi = (255, 255, 255)
    mid = (200, 200, 205)
    shade = (103, 101, 102)
    a[thick, :3] = metal
    a[thick, 3] = 255
    # continuous highlight ridge along top of spoon
    for y, x in zip(*np.where(thick)):
        up_clear = (y == 0) or (not thick[y - 1, x])
        dn_clear = (y == h - 1) or (not thick[y + 1, x])
        if up_clear:
            a[y, x, :3] = hi
        elif dn_clear:
            a[y, x, :3] = shade
        elif y > 0 and thick[y - 1, x] and a[y - 1, x, 0] == 255:
            a[y, x, :3] = mid
    # bowl near mouth (left end): round blob
    left_x = int(sx.min())
    bowl_cy = int(np.median(sy[sx <= left_x + 4]))
    bowl_cx = left_x + 2
    for dy in range(-4, 5):
        for dx in range(-4, 6):
            if dy * dy + dx * dx <= 18:
                yy, xx = bowl_cy + dy, bowl_cx + dx
                if 0 <= yy < h and 0 <= xx < w:
                    a[yy, xx, :3] = mid if dy * dy + dx * dx > 6 else hi
                    a[yy, xx, 3] = 255
                    if dy * dy + dx * dx >= 14:
                        a[yy, xx, :3] = shade
    # bright glint
    a[bowl_cy - 1, bowl_cx, :3] = hi
    a[bowl_cy - 2, bowl_cx + 1, :3] = hi
    return Image.fromarray(a, "RGBA")

def fix_teknium_smirk(native: Image.Image) -> Image.Image:
    """Readable 2–3px smirk with shading under the visor."""
    a = np.asarray(native).copy()
    h, w = a.shape[:2]
    m = a[..., 3] > 0
    rgb = a[..., :3].astype(np.int16)
    ys, xs = np.where(m)
    if not len(ys):
        return native
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    # find visor (red/white band) bottom
    visor = m & (((rgb[..., 0] > 180) & (rgb[..., 1] < 80)) | ((rgb.min(-1) > 220) & (np.arange(h)[:, None] < y0 + int(0.45 * (y1 - y0)))))
    if visor.any():
        my = int(np.where(visor)[0].max()) + 4
    else:
        my = y0 + int(0.42 * (y1 - y0))
    mx = (x0 + x1) // 2 + 4
    skin = (247, 190, 138)
    shadow = (179, 118, 79)

    def setp(y, x, col):
        if 0 <= y < h and 0 <= x < w and a[y, x, 3] > 0:
            a[y, x, :3] = col

    # clear a small mouth pad to skin first
    for dy in range(-1, 3):
        for dx in range(-6, 8):
            setp(my + dy, mx + dx, skin)
    # smirk curve: flat then lifts on right (asymmetric grin)
    # row 0: outline lip
    coords = [
        (0, -5), (0, -4), (0, -3), (0, -2), (0, -1), (0, 0), (0, 1), (0, 2),
        (1, 3), (1, 4), (1, 5), (0, 6),
    ]
    for dy, dx in coords:
        setp(my + dy, mx + dx, OUTLINE)
    # upper lip shade
    for dx in range(-4, 4):
        setp(my - 1, mx + dx, shadow)
    # corner crease
    setp(my + 1, mx + 5, shadow)
    setp(my + 2, mx + 4, shadow)
    return Image.fromarray(a, "RGBA")

def fix_southpaw_vest(native: Image.Image) -> Image.Image:
    """Solid near-black vest with clear silver studs."""
    a = np.asarray(native).copy()
    h, w = a.shape[:2]
    m = a[..., 3] > 0
    rgb = a[..., :3].astype(np.int16)
    ys, xs = np.where(m)
    if not len(ys):
        return native
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    # torso band below face (~52% down)
    ty0 = y0 + int(0.52 * (y1 - y0))
    torso = m.copy(); torso[:ty0] = False
    # hair = warm auburn — protect
    hair = (rgb[..., 0] > 100) & (rgb[..., 0] > rgb[..., 2] + 30) & (rgb[..., 1] < rgb[..., 0] + 10)
    # skin = peach
    skin = (rgb[..., 0] > 180) & (rgb[..., 1] > 140) & (rgb[..., 2] > 100) & (rgb[..., 0] - rgb[..., 2] < 80)
    # guitar frets/wood — warm brown mid, protect right side prop
    # vest candidates: currently grey / dark / mid-neutral in torso, not hair/skin
    vest = torso & ~hair & ~skin
    # also include mid greys that should be vest
    greyish = (np.abs(rgb[..., 0].astype(int) - rgb[..., 1]) < 25) & (np.abs(rgb[..., 1].astype(int) - rgb[..., 2]) < 25)
    vest |= torso & greyish & (rgb.mean(-1) < 160) & ~hair
    # teeth white in face — already above ty0
    BLACK = (8, 8, 10)
    DARK = (23, 23, 26)
    STUD = (180, 180, 190)
    STUD_HI = (255, 255, 255)
    # paint vest body dark
    for y, x in zip(*np.where(vest)):
        # keep existing bright studs
        if rgb[y, x].min() > 170:
            continue
        a[y, x, :3] = BLACK if rgb[y, x].mean() < 100 else DARK
    # place clear studs along shoulder straps (left and right of chest)
    # find vest columns
    vys, vxs = np.where(vest)
    if len(vys):
        # left strap: leftmost vest column cluster near ty0
        top = vest & (np.arange(h)[:, None] < ty0 + 12)
        if top.any():
            ty, tx = np.where(top)
            left_x = int(np.percentile(tx, 15))
            right_x = int(np.percentile(tx, 85))
            mid_y = int(np.percentile(ty, 40))
            for cx in (left_x, left_x + 3, right_x - 3, right_x):
                for i, yy in enumerate(range(mid_y, min(h - 2, mid_y + 18), 4)):
                    if a[yy, cx, 3] > 0 and not hair[yy, cx]:
                        a[yy, cx, :3] = STUD_HI
                        if a[yy + 1, cx, 3] > 0:
                            a[yy + 1, cx, :3] = STUD
                        if cx + 1 < w and a[yy, cx + 1, 3] > 0:
                            a[yy, cx + 1, :3] = STUD
    return Image.fromarray(a, "RGBA")

def kyle_cleanup_pass(native: Image.Image, key: str, pal: list) -> Image.Image:
    """Pixel-level cleanup on native 128 grid (no new gens)."""
    n = scrub_fringe_hard(native)
    n = smooth_silhouette(n)
    if key == "don_piedro":
        n = fix_don_spoon(n)
    if key == "teknium":
        n = fix_teknium_smirk(n)
    if key == "southpaw":
        n = fix_southpaw_vest(n)
    n = eye_highlights(n, key)
    n = scrub_fringe_hard(n)
    n = snap_palette(n, pal)
    n = fill_internal_holes(n)
    n = outline_silhouette(n)
    # final fringe after outline (outline can leave 1px tips)
    n = scrub_fringe_hard(n)
    n = outline_silhouette(n)
    return n


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
    n = kyle_cleanup_pass(n, key, pal)
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
