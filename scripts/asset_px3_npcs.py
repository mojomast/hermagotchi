#!/usr/bin/env python3
"""launch-003 NPCs (Clawpocalypse cameo hosts, not playable): green-keyed sources ->
48x48 native portrait + ~28px idle bust (2 frames) -> nearest upscale -> assets/px3/npcs/, assets/npcs.json.

Pets stay on the 32-grid in asset_px3; NPCs use a modestly higher native grid so silhouettes
and signature props stay readable. Reference art: Clawpocalypse title-screen cutouts under
assets/cine/title/<id>.png and cinematic intro panels (NOT hero sprites or portraits/).
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image
from asset_build import key_green, SRC, A
from asset_px3 import to_native_mode

# NPC-only grid (pets remain N=32 / FACTOR=16 in asset_px3)
NPC_N = 48
NPC_FACTOR = 10          # 48*10 = 480 display
PORT_COLORS = 24         # allow a few more colours than pets
BUST_COLORS = 16
PORT_H = 44
BUST_H = 28

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

def place_npc(native, x, y):
    cv = Image.new("RGBA", (NPC_N, NPC_N))
    cv.paste(native, (x, y), native)
    return cv

def up_npc(cv):
    return cv.resize((cv.width * NPC_FACTOR, cv.height * NPC_FACTOR), Image.NEAREST)

def main():
    out = A / "px3" / "npcs"; out.mkdir(parents=True, exist_ok=True); entries = []
    for e in NPCS:
        key = e["id"].split(".")[1]
        src = SRC / f"px3_npc_{key}_v3.jpg"
        k = key_green(src)
        bb = k.getchannel("A").getbbox(); w, h = bb[2] - bb[0], bb[3] - bb[1]
        port = to_native_mode(k, PORT_COLORS, **({"height": PORT_H} if h >= w else {"width": PORT_H}))
        if port.width > NPC_N - 2:
            port = to_native_mode(k, PORT_COLORS, width=NPC_N - 2)
        if port.height > NPC_N - 1:
            port = to_native_mode(k, PORT_COLORS, height=NPC_N - 1)
        pcv = place_npc(port, (NPC_N - port.width) // 2, NPC_N - 1 - port.height)
        pp = out / f"{key}_portrait.png"; up_npc(pcv).save(pp, optimize=True)
        bust = to_native_mode(k, BUST_COLORS, **({"height": BUST_H} if h >= w else {"width": BUST_H}))
        if bust.width > NPC_N - 2:
            bust = to_native_mode(k, BUST_COLORS, width=NPC_N - 2)
        frames = []
        for f, dy in enumerate((0, 1)):   # 2-frame idle bob, 1 native px
            cv = place_npc(bust, (NPC_N - bust.width) // 2, NPC_N - 4 - bust.height + dy)
            fp = out / f"{key}_idle_{f}.png"; up_npc(cv).save(fp, optimize=True)
            frames.append({"path": f"px3/npcs/{fp.name}", "sha256": sha(fp)})
        entries.append({
            "id": e["id"], "name": e["name"], "role": e["role"], "ui_surface": e["ui_surface"], "playable": False,
            "portrait": {"path": f"px3/npcs/{pp.name}", "sha256": sha(pp), "native": [NPC_N, NPC_N], "factor": NPC_FACTOR},
            "idle": {"frames": frames, "frame_ms": 500}, "flavor_lines": e["lines"],
            "source": f"source/{src.name}",
            "reference": f"Clawpocalypse title-screen cutout assets/cine/title/{e['claw_hero']}.png (+ cinematic intro panel)",
            "rights_note": "Cameo of Kyle's Clawpocalypse hero characters, added at his request. Fictional game characters; the lines are playful in-game flavor and make no claims about any real person.",
        })
    (A / "npcs.json").write_text(json.dumps({"schema": "hermagotchi-npcs-v1", "asset_pack_id": "launch-003", "npcs": entries}, indent=2) + "\n")

    # preview sheet: portraits + idle busts
    cell = NPC_N * NPC_FACTOR
    sheet = Image.new("RGB", (4 * cell, cell + cell // 2), (236, 232, 245))
    for i, en in enumerate(entries):
        p = Image.open(A / en["portrait"]["path"]).convert("RGBA")
        sheet.paste(p, (i * cell, 0), p)
        b = Image.open(A / en["idle"]["frames"][0]["path"]).convert("RGBA").resize((cell // 2, cell // 2), Image.NEAREST)
        sheet.paste(b, (i * cell + cell // 4, cell), b)
    sheet.save("/tmp/px3_npcs.png")

    # Operator preview: copy /tmp/px3_npcs.png; build title-vs-NPC compare sheet outside the pack.
    print("npcs:", len(entries), "native", NPC_N, "factor", NPC_FACTOR)

if __name__ == "__main__":
    main()
