#!/usr/bin/env python3
"""launch-003 NPCs (Clawpocalypse cameo hosts, not playable): magenta-keyed sources ->
32x32 native portrait + 20px idle bust (2 frames) -> x16 nearest -> assets/px3/npcs/, assets/npcs.json."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
from asset_build import SRC, A
from asset_px3 import N, FACTOR, to_native_mode, place_native, up

def key_magenta(path):
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    k = np.minimum(r, b * 1.6) - g - 60          # magenta dominance (bg ~ #DC0080)
    alpha = np.clip(1 - (k - 30) / 60, 0, 1)
    lab, n = ndimage.label(alpha > 0.5); sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= sizes.max() * 0.02])
    return Image.fromarray(np.dstack([im, alpha * keep * 255]).astype(np.uint8), "RGBA")

NPCS = [
  {"id": "npc.don_piedro", "name": "Don Piedro", "role": "Cosmetics shopkeeper. Carries a big spoon and is Hermes' #1 fan.", "ui_surface": "shop",
   "lines": ["Fresh hats! Still warm from the forge... I mean the oven.", "Every pet deserves a crown. Some deserve two.", "Hermes shops here. Probably. In spirit.", "No refunds, but I'll stir your Bits with my lucky spoon.", "That scarf? It's you. It's absolutely you."]},
  {"id": "npc.nous_girl", "name": "Nous Girl", "role": "Lobby and chat host who posts moderation notices. Carries an audio cable.", "ui_surface": "lobby",
   "lines": ["Plugged in! Lobby's live.", "Keep it friendly. Cable's long, patience is short.", "Heads up: that message got muted. Be kind, try again.", "New challenger in the lobby. Say hi!", "Signal clear. Chat on."]},
  {"id": "npc.teknium", "name": "Teknium", "role": "Trainer for bot practice who explains combat rules. Carries an energy blade.", "ui_surface": "practice",
   "lines": ["Practice bouts don't touch your rating. Swing freely.", "Six rounds, one pet each. Read the cooldowns.", "Your agent picks the move. You pick the policy.", "Blade's charged. Let's run another seed.", "Status effects stack less than you think. Test it."]},
  {"id": "npc.turbofit", "name": "Turbofit", "role": "Arena announcer for the leaderboard and bounties. Carries an axe-shaped guitar.", "ui_surface": "leaderboard",
   "lines": ["LADIES, GENTS AND AGENTS... the leaderboard!", "New bounty dropped. Shred it before it expires!", "That win streak? Pure distortion.", "Top of the board gets the loudest riff.", "Encore! Season standings updated."]},
]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    out = A / "px3" / "npcs"; out.mkdir(parents=True, exist_ok=True); entries = []
    for e in NPCS:
        key = e["id"].split(".")[1]; src = SRC / f"px3_npc_{key}_v1.jpg"; k = key_magenta(src)
        bb = k.getchannel("A").getbbox(); w, h = bb[2] - bb[0], bb[3] - bb[1]
        port = to_native_mode(k, 18, **({"height": 30} if h >= w else {"width": 30}))
        pcv = place_native(port, (N - port.width) // 2, N - 1 - port.height)
        pp = out / f"{key}_portrait.png"; up(pcv).save(pp, optimize=True)
        bust = to_native_mode(k, 10, **({"height": 20} if h >= w else {"width": 20}))
        frames = []
        for f, dy in enumerate((0, 1)):   # 2-frame idle bob, 1 native px
            cv = place_native(bust, (N - bust.width) // 2, N - 4 - bust.height + dy)
            fp = out / f"{key}_idle_{f}.png"; up(cv).save(fp, optimize=True)
            frames.append({"path": f"px3/npcs/{fp.name}", "sha256": sha(fp)})
        entries.append({"id": e["id"], "name": e["name"], "role": e["role"], "ui_surface": e["ui_surface"], "playable": False,
            "portrait": {"path": f"px3/npcs/{pp.name}", "sha256": sha(pp), "native": [N, N], "factor": FACTOR},
            "idle": {"frames": frames, "frame_ms": 500}, "flavor_lines": e["lines"], "source": f"source/{src.name}",
            "rights_note": "Cameo of Kyle's Clawpocalypse hero characters, added at his request. Fictional game characters; the lines are playful in-game flavor and make no claims about any real person."})
    (A / "npcs.json").write_text(json.dumps({"schema": "hermagotchi-npcs-v1", "asset_pack_id": "launch-003", "npcs": entries}, indent=2) + "\n")
    sheet = Image.new("RGB", (4 * 512, 512 + 256), (236, 232, 245))
    for i, en in enumerate(entries):
        p = Image.open(A / en["portrait"]["path"]).convert("RGBA"); sheet.paste(p, (i * 512, 0), p)
        b = Image.open(A / en["idle"]["frames"][0]["path"]).convert("RGBA").resize((256, 256), Image.NEAREST); sheet.paste(b, (i * 512 + 128, 512), b)
    sheet.save("/workspace/hermagotchi-art-preview/px3_npcs.png"); sheet.save("/tmp/px3_npcs_v2.png")
    print("npcs:", len(entries))

if __name__ == "__main__":
    main()
