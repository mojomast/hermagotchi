#!/usr/bin/env python3
"""launch-003 NPCs (Clawpocalypse cameo hosts, not playable).

Green-keyed HD sources -> native 128 grid portrait + dialog bust + 2-frame idle
-> nearest upscale -> assets/px3/npcs/, assets/npcs.json.

Pets stay on the 32-grid in asset_px3. NPCs are higher-def so faces read.
Primary reference: Clawpocalypse cinematic portraits under
assets/cine/v3/portraits/<id>.png (Southpaw -> turbofit.png). Title cutouts are
secondary. Not heroes/portraits or in-game sprites.
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
NPC_FACTOR = 4           # 128*4 = 512 display
PORT_COLORS = 32
BUST_COLORS = 28
PORT_H = 120             # nearly fills 128 canvas
BUST_H = 96              # dialog bust
IDLE_H = 72

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

def key_chroma_green(path: Path) -> Image.Image:
    """Key flat chroma-green bg via edge flood so teal/seafoam hair (Teknium) survives."""
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    # pure screen green: strong G dominance + high green
    is_bg = (g > 80) & ((g - np.maximum(r, b)) > 35) & (g > (r + b) * 0.55)
    h, w = is_bg.shape
    edge = np.zeros_like(is_bg, bool)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    seed = is_bg & edge
    # dilate flood through connected bg
    mask = seed.copy()
    struct = ndimage.generate_binary_structure(2, 1)
    for _ in range(max(h, w)):
        grown = ndimage.binary_dilation(mask, structure=struct) & is_bg
        if np.array_equal(grown, mask):
            break
        mask = grown
    alpha = np.where(mask, 0.0, 1.0).astype(np.float32)
    # despill residual green fringe on opaque edge
    fringe = (~mask) & ndimage.binary_dilation(mask, structure=struct)
    g2 = g.copy()
    m = np.maximum(r, b)
    g2[fringe] = np.minimum(g[fringe], m[fringe] + 8)
    out = np.dstack([r, g2, b, alpha * 255]).astype(np.uint8)
    # drop tiny detached specks
    lab, n = ndimage.label(out[..., 3] > 128)
    if n:
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= sizes.max() * 0.01])
        out[..., 3] = np.where(keep, out[..., 3], 0)
    return Image.fromarray(out, "RGBA")

def brighten_darks(keyed: Image.Image, floor: float = 55.0, lift: float = 48.0) -> Image.Image:
    """Lift dark outfit pixels (Teknium green coat, Southpaw black vest) so seams/studs read."""
    a = np.asarray(keyed).copy()
    rgb = a[..., :3].astype(np.float32)
    lum = rgb.mean(-1)
    opaque = a[..., 3] > 128
    # skip near-black outline
    dark = opaque & (lum < 110) & (lum > 12)
    # stronger lift the darker it is
    t = np.clip((110 - lum) / 110.0, 0, 1)
    add = (lift * t)[..., None]
    rgb[dark] = np.clip(rgb[dark] + add[dark], 0, 255)
    # also nudge very dark toward a readable charcoal rather than crushed black
    crush = opaque & (lum <= 35) & (lum > 8)
    rgb[crush] = np.clip(rgb[crush] * 1.35 + 18, 0, 255)
    a[..., :3] = rgb.astype(np.uint8)
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

def main():
    out = A / "px3" / "npcs"; out.mkdir(parents=True, exist_ok=True); entries = []
    for e in NPCS:
        key = e["id"].split(".")[1]
        src = SRC / f"px3_npc_{key}_v4.jpg"
        k = brighten_darks(key_chroma_green(src))
        port = fit_native(k, PORT_COLORS, PORT_H)
        pcv = place_npc(port, (NPC_N - port.width) // 2, NPC_N - 1 - port.height)
        pp = out / f"{key}_portrait.png"; up_npc(pcv).save(pp, optimize=True)

        bust = fit_native(k, BUST_COLORS, BUST_H)
        bcv = place_npc(bust, (NPC_N - bust.width) // 2, NPC_N - 1 - bust.height)
        bp = out / f"{key}_dialog.png"; up_npc(bcv).save(bp, optimize=True)

        idle = fit_native(k, BUST_COLORS, IDLE_H)
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
            "reference": f"Clawpocalypse cinematic portrait assets/cine/v3/portraits/{e['claw_hero']}.png (primary); title cutout assets/cine/title/{e['claw_hero']}.png (secondary)",
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
