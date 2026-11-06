#!/usr/bin/env python3
"""Hand-authored NPC pixel portraits — NO image gen, NO v6/v7 snap.

Design native: 64×64 busts drawn with explicit shapes/pixels.
Contract: nearest ×2 → 128 canvas, then ×4 display (512).
Refs (eyes only): Clawpocalypse cine/v3/portraits (Southpaw=turbofit).
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "assets"
OUT = A / "px3" / "npcs"

NPC_N = 128
NPC_FACTOR = 4
DESIGN = 64  # author here, NN upscale to 128
OUTLINE = (16, 14, 28)

# ---- named palettes (12–16, upper-left light ramps) ----
DON = {
    "out": OUTLINE,
    "fur_d": (48, 28, 18), "fur": (96, 62, 36), "fur_h": (148, 108, 68), "muzzle": (198, 168, 128),
    "arm_d": (180, 176, 172), "arm": (236, 232, 228), "arm_h": (255, 255, 255),
    "gold": (200, 150, 50), "gold_h": (240, 200, 90),
    "blue": (20, 48, 110), "blue_h": (40, 80, 160),
    "red": (180, 16, 28), "red_h": (240, 50, 50),
    "spoon": (150, 150, 155), "spoon_h": (230, 230, 235), "spoon_s": (90, 90, 95),
}
NOUS = {
    "out": OUTLINE,
    "hair": (22, 18, 20), "hair_m": (46, 40, 44), "hair_h": (90, 86, 88),
    "skin": (248, 228, 210), "skin_s": (220, 180, 150), "skin_d": (190, 140, 115),
    "eye": (20, 16, 18), "white": (254, 254, 253),
    "hp": (236, 236, 238), "hp_s": (170, 170, 175), "hp_d": (120, 120, 125),
    "shirt": (245, 245, 247), "shirt_s": (200, 200, 205),
    "lip": (160, 90, 80),
}
TEK = {
    "out": OUTLINE,
    "hair": (8, 110, 95), "hair_m": (40, 180, 150), "hair_h": (110, 230, 190),
    "leaf": (40, 140, 50), "leaf_d": (20, 90, 30),
    "skin": (247, 190, 138), "skin_s": (210, 150, 100), "skin_d": (170, 110, 75),
    "jack": (10, 100, 70), "jack_d": (6, 70, 48), "jack_h": (40, 140, 100),
    "stripe": (248, 248, 245), "red": (220, 12, 36), "white": (255, 255, 255),
    "zip": (200, 200, 205),
}
SOUTH = {
    "out": OUTLINE,
    "hair_d": (70, 18, 14), "hair": (150, 55, 30), "hair_m": (200, 100, 50), "hair_h": (240, 160, 90),
    "skin": (240, 190, 150), "skin_s": (210, 150, 110), "skin_d": (170, 110, 80),
    "vest": (12, 12, 14), "vest_m": (28, 28, 32),
    "stud": (200, 200, 210), "stud_h": (255, 255, 255),
    "teeth": (255, 255, 255), "lip": (140, 60, 50),
    "git": (90, 55, 30), "git_d": (50, 28, 14), "git_h": (180, 180, 190),
    "eye": (20, 18, 22),
}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class Canvas:
    def __init__(self, w=DESIGN, h=DESIGN):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)

    def p(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x, :3] = c
            self.a[y, x, 3] = 255

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.p(x, y, c)

    def ellipse(self, cx, cy, rx, ry, c, soft=False):
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                if ry == 0 or rx == 0:
                    continue
                v = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
                if v <= 1.0:
                    self.p(x, y, c)

    def line(self, x0, y0, x1, y1, c, thick=1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx - dy
        x, y = x0, y0
        while True:
            for t in range(-(thick // 2), thick - thick // 2):
                if dx >= dy:
                    self.p(x, y + t, c)
                else:
                    self.p(x + t, y, c)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy; x += sx
            if e2 < dx:
                err += dx; y += sy

    def disc(self, cx, cy, r, c):
        self.ellipse(cx, cy, r, r, c)

    def outline(self, col=OUTLINE):
        m = self.a[..., 3] > 0
        edge = m & ~ndimage.binary_erosion(m, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
        self.a[edge, :3] = col

    def img(self) -> Image.Image:
        return Image.fromarray(self.a, "RGBA")

# ---------------- character drawers (64×64) ----------------

def draw_don(blink=False) -> Canvas:
    c, P = Canvas(), DON
    # shoulders / armour body
    c.ellipse(32, 52, 26, 16, P["arm"])
    c.ellipse(32, 54, 22, 12, P["arm_d"])  # shade lower-right
    # blue undersuit collar
    c.ellipse(32, 42, 10, 6, P["blue"])
    c.ellipse(28, 40, 5, 4, P["blue_h"])  # UL light
    # gold trim on pauldron L
    c.ellipse(14, 46, 8, 7, P["arm"])
    for y in range(40, 55):
        for x in range(6, 22):
            if ((x - 14) / 8) ** 2 + ((y - 46) / 7) ** 2 <= 1:
                c.p(x, y, P["arm"] if x < 16 else P["arm_d"])
    c.line(8, 42, 20, 40, P["gold"], 1)
    c.line(8, 50, 20, 52, P["gold"], 1)
    c.p(12, 44, P["gold_h"]); c.p(14, 45, P["gold"])  # star-ish
    c.p(14, 43, P["gold_h"]); c.p(16, 45, P["gold"]); c.p(14, 47, P["gold"])
    # chest clasp
    c.disc(32, 50, 2, P["gold"]); c.p(32, 49, P["gold_h"])
    # head
    c.ellipse(34, 26, 16, 15, P["fur"])
    c.ellipse(38, 28, 10, 10, P["fur_d"])  # shade R
    c.ellipse(28, 22, 8, 7, P["fur_h"])  # UL highlight
    # ears
    c.disc(22, 14, 4, P["fur"]); c.disc(22, 14, 2, P["fur_d"])
    c.disc(46, 14, 4, P["fur"]); c.disc(46, 14, 2, P["fur_d"])
    # muzzle
    c.ellipse(38, 32, 9, 6, P["muzzle"])
    c.ellipse(42, 33, 5, 4, P["fur_h"])
    c.disc(44, 30, 2, P["out"])  # nose
    c.p(43, 29, P["fur_h"])
    # brow
    c.line(24, 22, 32, 20, P["fur_d"], 1)
    # open eye (L) — skip if blink
    if not blink:
        c.rect(26, 24, 30, 27, P["out"])
        c.p(27, 25, P["fur_d"]); c.p(28, 24, P["arm_h"])  # highlight
    else:
        c.line(26, 26, 30, 26, P["out"], 1)
    # red monocle (R eye)
    c.disc(40, 25, 4, P["gold"])
    c.disc(40, 25, 3, P["red"])
    c.p(39, 24, P["red_h"]); c.p(38, 23, P["arm_h"])
    c.line(44, 25, 48, 22, P["out"], 1)  # cord
    # mouth
    c.line(34, 36, 42, 36, P["fur_d"], 1)
    # BIG spoon slung behind R shoulder (not covering monocle)
    # bowl sits above R pauldron / behind head-right
    c.ellipse(52, 16, 9, 7, P["spoon"])
    c.ellipse(50, 14, 5, 4, P["spoon_h"])
    c.ellipse(54, 18, 5, 4, P["spoon_s"])
    c.p(48, 13, P["arm_h"])
    # handle diagonal up-right from bowl
    for i in range(0, 14):
        x = 58 + i // 2; y = 12 - i
        for tt in range(-2, 3):
            c.p(x, y + tt, P["spoon"])
        c.p(x, y - 2, P["spoon_h"])
        c.p(x, y + 2, P["spoon_s"])
    # thin strap from monocle already drawn; reinforce monocle on top of anything
    c.disc(40, 25, 4, P["gold"])
    c.disc(40, 25, 3, P["red"])
    c.p(39, 24, P["red_h"]); c.p(38, 23, P["arm_h"])
    c.outline()
    return c

def draw_nous(blink=False) -> Canvas:
    c, P = Canvas(), NOUS
    # turtleneck
    c.ellipse(32, 52, 24, 14, P["shirt"])
    c.ellipse(36, 54, 16, 10, P["shirt_s"])  # shade R
    c.ellipse(26, 48, 10, 6, P["white"])  # UL
    # collar ring
    c.ellipse(32, 42, 9, 5, P["shirt_s"])
    c.ellipse(32, 40, 7, 3, P["shirt"])
    # neck
    c.rect(28, 36, 36, 42, P["skin"])
    c.rect(34, 36, 36, 42, P["skin_s"])
    # head
    c.ellipse(32, 26, 14, 15, P["skin"])
    c.ellipse(36, 28, 8, 10, P["skin_s"])
    c.ellipse(26, 22, 6, 6, P["white"])  # cheek light
    # black bob
    c.ellipse(32, 20, 16, 14, P["hair"])
    # bangs
    c.rect(20, 16, 44, 24, P["hair"])
    for x, y in [(22, 18), (26, 17), (30, 16), (34, 17), (38, 18), (42, 19)]:
        c.p(x, y, P["hair"])
    # hair highlight UL
    c.line(22, 14, 28, 12, P["hair_h"], 1)
    c.p(24, 13, P["hair_h"]); c.p(25, 14, P["hair_m"])
    # side hair shape
    c.ellipse(18, 28, 4, 10, P["hair"])
    c.ellipse(46, 28, 4, 10, P["hair"])
    c.ellipse(17, 34, 3, 4, P["hair_m"])
    # face window (punch skin over bangs lower)
    c.ellipse(32, 28, 10, 8, P["skin"])
    c.ellipse(36, 30, 6, 6, P["skin_s"])
    # eyes
    if not blink:
        c.rect(23, 25, 28, 30, P["eye"])
        c.p(24, 26, P["hair_m"]); c.p(25, 25, P["white"])
        c.rect(36, 25, 41, 30, P["eye"])
        c.p(37, 26, P["hair_m"]); c.p(38, 25, P["white"])
        c.p(23, 24, P["out"]); c.p(41, 24, P["out"])
    else:
        c.line(24, 28, 28, 28, P["out"], 1)
        c.line(36, 28, 40, 28, P["out"], 1)
    # brows
    c.line(23, 24, 29, 23, P["hair"], 1)
    c.line(35, 23, 41, 24, P["hair"], 1)
    # nose
    c.p(32, 30, P["skin_d"]); c.p(33, 31, P["skin_d"])
    # mouth
    c.line(29, 34, 35, 34, P["lip"], 1)
    # headphones — cups
    c.disc(16, 26, 6, P["hp"])
    c.disc(16, 26, 4, P["hp_s"])
    c.disc(16, 26, 2, P["hp_d"])
    c.p(14, 24, P["white"])  # UL glint
    c.disc(48, 26, 6, P["hp"])
    c.disc(48, 26, 4, P["hp_s"])
    c.disc(48, 26, 2, P["hp_d"])
    c.p(46, 24, P["white"])
    # headband
    for x in range(18, 47):
        y = 12 + int(0.015 * (x - 32) ** 2)
        c.p(x, y, P["hp"]); c.p(x, y + 1, P["hp_s"])
        if x < 30:
            c.p(x, y, P["white"])
    c.outline()
    return c

def draw_teknium(blink=False) -> Canvas:
    c, P = Canvas(), TEK
    # jacket
    c.ellipse(32, 52, 24, 14, P["jack"])
    c.ellipse(38, 54, 14, 10, P["jack_d"])
    c.ellipse(24, 48, 10, 8, P["jack_h"])
    # collar
    c.ellipse(32, 40, 10, 5, P["jack_d"])
    c.rect(28, 38, 36, 44, P["jack"])
    # zipper
    c.line(32, 42, 32, 60, P["zip"], 1)
    c.p(32, 44, P["white"])
    # shoulder racing stripes (parallel)
    for dx in (0, 2):
        c.line(16 + dx, 42, 20 + dx, 60, P["stripe"], 1)
        c.line(46 - dx, 42, 42 - dx, 60, P["stripe"], 1)
    # neck
    c.rect(28, 34, 36, 40, P["skin"])
    c.rect(34, 34, 36, 40, P["skin_s"])
    # head
    c.ellipse(32, 24, 13, 14, P["skin"])
    c.ellipse(36, 26, 8, 10, P["skin_s"])
    c.ellipse(26, 20, 5, 5, P["skin"])
    # spiky teal hair
    spikes = [
        (32, 6, 4), (24, 8, 3), (40, 8, 3), (18, 14, 3), (46, 14, 3),
        (28, 4, 3), (36, 4, 3), (20, 10, 2), (44, 10, 2), (32, 2, 2),
    ]
    for sx, sy, r in spikes:
        c.disc(sx, sy, r, P["hair"])
        c.p(sx - 1, sy - 1, P["hair_h"])
        c.p(sx + 1, sy + 1, P["hair"])
    c.ellipse(32, 14, 14, 8, P["hair"])
    c.ellipse(28, 12, 6, 4, P["hair_h"])
    c.ellipse(38, 14, 6, 5, P["hair_m"])
    # leaf behind L ear
    c.ellipse(18, 18, 3, 5, P["leaf"])
    c.line(18, 15, 18, 22, P["leaf_d"], 1)
    # visor (covers eyes) — red/white diagonal stripes
    c.rect(20, 20, 44, 28, P["white"])
    for i, x0 in enumerate(range(20, 44, 3)):
        col = P["red"] if i % 2 == 0 else P["white"]
        for y in range(21, 28):
            for x in range(x0, min(x0 + 3, 45)):
                # diagonal offset
                xx = x + (y - 21)
                if 20 <= xx <= 44:
                    c.p(xx, y, col)
    c.line(20, 20, 44, 20, P["white"], 1)
    c.line(20, 28, 44, 28, P["out"], 1)
    # smirk
    c.line(30, 32, 38, 32, P["out"], 1)
    c.p(38, 31, P["out"]); c.p(39, 30, P["skin_d"])
    c.p(31, 33, P["skin_d"]); c.p(36, 33, P["skin_d"])
    # nose hint
    c.p(34, 30, P["skin_d"])
    c.outline()
    return c

def draw_southpaw(blink=False) -> Canvas:
    c, P = Canvas(), SOUTH
    # guitar headstock behind R shoulder
    c.rect(48, 20, 58, 36, P["git_d"])
    c.rect(50, 18, 60, 22, P["git"])
    for i, x in enumerate(range(51, 60, 2)):
        c.p(x, 19, P["stud_h"]); c.p(x, 21, P["git_h"])  # tuning pegs
    c.line(48, 36, 44, 48, P["git"], 2)  # neck
    # torso / vest
    c.ellipse(30, 54, 22, 14, P["vest"])
    c.ellipse(34, 56, 14, 8, P["vest_m"])
    # open chest skin V
    c.ellipse(30, 48, 7, 5, P["skin"])
    c.ellipse(28, 47, 3, 3, P["skin"])
    c.ellipse(32, 49, 4, 3, P["skin_s"])
    # vest straps + studs
    c.line(18, 42, 24, 58, P["vest"], 3)
    c.line(36, 42, 42, 58, P["vest"], 3)
    for y in range(44, 58, 4):
        c.p(19, y, P["stud_h"]); c.p(20, y + 1, P["stud"])
        c.p(40, y, P["stud_h"]); c.p(41, y + 1, P["stud"])
    # neck
    c.rect(26, 36, 36, 44, P["skin"])
    c.rect(32, 36, 36, 44, P["skin_s"])
    # head
    c.ellipse(30, 24, 13, 14, P["skin"])
    c.ellipse(34, 26, 8, 10, P["skin_s"])
    c.ellipse(24, 20, 5, 5, P["skin"])
    # long curly auburn hair — layered blobs
    curls = [
        (30, 10, 14, 8), (20, 16, 8, 10), (42, 14, 9, 12),
        (16, 28, 6, 12), (44, 30, 7, 14), (24, 8, 6, 5),
        (36, 6, 7, 5), (12, 36, 5, 8), (48, 40, 5, 8),
        (28, 4, 5, 4), (38, 12, 5, 6),
    ]
    for cx, cy, rx, ry in curls:
        c.ellipse(cx, cy, rx, ry, P["hair"])
    # highlights UL
    c.ellipse(24, 10, 4, 3, P["hair_h"])
    c.ellipse(32, 6, 3, 2, P["hair_h"])
    c.ellipse(18, 20, 3, 4, P["hair_m"])
    # shade curls R
    c.ellipse(44, 28, 5, 8, P["hair_d"])
    c.ellipse(14, 34, 3, 5, P["hair_d"])
    # face clear
    c.ellipse(30, 26, 10, 9, P["skin"])
    c.ellipse(34, 28, 6, 7, P["skin_s"])
    # brows
    c.line(22, 22, 28, 21, P["hair_d"], 1)
    c.line(34, 21, 40, 22, P["hair_d"], 1)
    # eyes
    if not blink:
        c.rect(24, 24, 27, 27, P["eye"])
        c.p(25, 24, P["teeth"])  # highlight
        c.rect(36, 24, 39, 27, P["eye"])
        c.p(37, 24, P["teeth"])
    else:
        c.line(24, 26, 27, 26, P["out"], 1)
        c.line(36, 26, 39, 26, P["out"], 1)
    # nose
    c.p(31, 28, P["skin_d"]); c.p(32, 29, P["skin_d"])
    # BIG grin
    c.rect(24, 32, 40, 36, P["lip"])
    c.rect(25, 33, 39, 35, P["teeth"])
    c.line(24, 32, 40, 32, P["out"], 1)
    c.line(24, 36, 40, 36, P["out"], 1)
    c.p(24, 33, P["out"]); c.p(40, 33, P["out"])
    # tooth gaps hint
    c.p(30, 34, P["skin_s"]); c.p(34, 34, P["skin_s"])
    c.outline()
    return c

DRAW = {
    "don_piedro": draw_don,
    "nous_girl": draw_nous,
    "teknium": draw_teknium,
    "southpaw": draw_southpaw,
}

NPCS_META = [
  {"id": "npc.don_piedro", "name": "Don Piedro", "role": "Cosmetics shopkeeper. Carries a big spoon and is Hermes' #1 fan.", "ui_surface": "shop", "claw_hero": "don_piedro",
   "lines": ["Fresh hats! Still warm from the forge... I mean the oven.", "Every pet deserves a crown. Some deserve two.", "Hermes shops here. Probably. In spirit.", "No refunds, but I'll stir your Bits with my lucky spoon.", "That scarf? It's you. It's absolutely you."]},
  {"id": "npc.nous_girl", "name": "Nous Girl", "role": "Lobby and chat host who posts moderation notices. Carries an audio cable.", "ui_surface": "lobby", "claw_hero": "nous_girl",
   "lines": ["Plugged in! Lobby's live.", "Keep it friendly. Cable's long, patience is short.", "Heads up: that message got muted. Be kind, try again.", "New challenger in the lobby. Say hi!", "Signal clear. Chat on."]},
  {"id": "npc.teknium", "name": "Teknium", "role": "Trainer for bot practice who explains combat rules. Carries an energy blade.", "ui_surface": "practice", "claw_hero": "teknium",
   "lines": ["Practice bouts don't touch your rating. Swing freely.", "Six rounds, one pet each. Read the cooldowns.", "Your agent picks the move. You pick the policy.", "Blade's charged. Let's run another seed.", "Status effects stack less than you think. Test it."]},
  {"id": "npc.southpaw", "name": "Southpaw", "role": "Arena announcer for the leaderboard and bounties. Carries an axe-shaped guitar.", "ui_surface": "leaderboard", "claw_hero": "turbofit",
   "lines": ["LADIES, GENTS AND AGENTS... the leaderboard!", "New bounty dropped. Shred it before it expires!", "That win streak? Pure distortion.", "Top of the board gets the loudest riff.", "Encore! Season standings updated."]},
]

def to_native128(design: Canvas, bob=0) -> Image.Image:
    """NN ×2 to 128, bottom-center place, optional 1px bob."""
    small = design.img().resize((DESIGN * 2, DESIGN * 2), Image.NEAREST)  # 128×128 content
    # content is already 128; place with vertical bob on canvas
    cv = Image.new("RGBA", (NPC_N, NPC_N), (0, 0, 0, 0))
    # design fills most of 64→128; slight bottom align
    y = max(0, min(NPC_N - small.height, 2 + bob))
    x = (NPC_N - small.width) // 2
    cv.paste(small, (x, y), small)
    return cv

def dialog_crop(port128: Image.Image) -> Image.Image:
    """Slightly tighter bust: crop top-heavy, scale back to 128."""
    a = np.asarray(port128)
    m = a[..., 3] > 0
    ys, xs = np.where(m)
    if not len(ys):
        return port128
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    # prefer upper body
    y1 = y0 + int(0.85 * (y1 - y0))
    crop = port128.crop((x0, y0, x1 + 1, y1 + 1))
    # scale to fit ~110 tall
    tw = min(120, int(crop.width * 110 / max(1, crop.height)))
    th = min(120, int(crop.height * tw / max(1, crop.width)))
    crop = crop.resize((tw, th), Image.NEAREST)
    cv = Image.new("RGBA", (NPC_N, NPC_N), (0, 0, 0, 0))
    cv.paste(crop, ((NPC_N - tw) // 2, NPC_N - th - 2), crop)
    return cv

def up(cv: Image.Image) -> Image.Image:
    return cv.resize((NPC_N * NPC_FACTOR, NPC_N * NPC_FACTOR), Image.NEAREST)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    old = {}
    if (A / "npcs.json").exists():
        old = {n["id"]: n for n in json.loads((A / "npcs.json").read_text())["npcs"]}
    entries = []
    for e in NPCS_META:
        key = e["id"].split(".")[1]
        drawer = DRAW[key]
        port = to_native128(drawer(blink=False), bob=0)
        bust = dialog_crop(port)
        idle0 = to_native128(drawer(blink=False), bob=0)
        idle1 = to_native128(drawer(blink=True), bob=1)
        pp = OUT / f"{key}_portrait.png"; up(port).save(pp, optimize=True)
        bp = OUT / f"{key}_dialog.png"; up(bust).save(bp, optimize=True)
        frames = []
        for f, im in enumerate((idle0, idle1)):
            fp = OUT / f"{key}_idle_{f}.png"; up(im).save(fp, optimize=True)
            frames.append({"path": f"px3/npcs/{fp.name}", "sha256": sha(fp)})
        flavor = old.get(e["id"], {}).get("flavor_lines", e["lines"])
        entries.append({
            "id": e["id"], "name": e["name"], "role": e["role"], "ui_surface": e["ui_surface"], "playable": False,
            "portrait": {"path": f"px3/npcs/{pp.name}", "sha256": sha(pp), "native": [NPC_N, NPC_N], "factor": NPC_FACTOR},
            "dialog": {"path": f"px3/npcs/{bp.name}", "sha256": sha(bp), "native": [NPC_N, NPC_N], "factor": NPC_FACTOR,
                       "notes": "Bust crop for dialog boxes"},
            "idle": {"frames": frames, "frame_ms": 500},
            "flavor_lines": flavor,
            "source": f"scripts/draw_npcs.py#{key}",
            "reference": (
                f"Clawpocalypse cinematic portrait assets/cine/v3/portraits/{e['claw_hero']}.png — "
                "hand-authored pixel map in scripts/draw_npcs.py (64→128 NN); "
                "no GenerateImage, not painterly, no v6/v7 snap"
            ),
            "rights_note": "Cameo of Kyle's Clawpocalypse hero characters, added at his request. Fictional game characters; the lines are playful in-game flavor and make no claims about any real person.",
        })
    (A / "npcs.json").write_text(json.dumps({"schema": "hermagotchi-npcs-v1", "asset_pack_id": "launch-003", "lines_ref": "npc_lines.json", "npcs": entries}, indent=2) + "\n")
    # preview sheet
    cell = NPC_N * NPC_FACTOR
    sheet = Image.new("RGB", (4 * cell, cell + cell // 2), (236, 232, 245))
    for i, en in enumerate(entries):
        p = Image.open(A / en["portrait"]["path"]).convert("RGBA")
        sheet.paste(p, (i * cell, 0), p)
        b = Image.open(A / en["dialog"]["path"]).convert("RGBA").resize((cell // 2, cell // 2), Image.NEAREST)
        sheet.paste(b, (i * cell + cell // 4, cell), b)
    sheet.save("/tmp/px3_npcs.png")
    print("draw_npcs: 4 hand-authored @64 → native", NPC_N)

if __name__ == "__main__":
    main()
