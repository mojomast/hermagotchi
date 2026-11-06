# Hermagotchi style guide (locked for launch-001)

**Style prompt core:** "Original indie creature-game character sprite … cozy futuristic 2D cel-shaded collectible monster, bold uniform dark navy outline, flat cel shading with one shadow tone, limited palette, strictly front-facing orthographic view, full body centered, wide empty margins. Perfectly flat solid pure chroma green #00FF00 background, no gradient, no cast shadow, no ground, no props, no text, no watermark."
**Accessory prompt core:** "Match the reference art style exactly … Draw ONLY a single detachable accessory, no character: {item}, front view, centered … flat #00FF00 background." Reference: `assets/source/byteblob_master_v1.jpg`.
**Rules:** outline is navy (~#0f1a33). No green as a main colour. One shadow tone. Faces must read at 96 px. No text baked into layers (the client draws title text on the ribbon).
**Canvas:** 512×512 RGBA, baseline y=448, safe x 65..447 / y 75..450. Item attach point is at (256,256).
**Species:** Byteblob (round gumdrop slime-robot, antenna, screen belly). Patchfox (sitting fox familiar, tall ears, plume tail, stitched cheek patch). Nullgeist (floating ghost, curling wisp tail, glitch cubes). Each species has its own silhouette.
**Palettes (procedural HSV):** byteblob aqua/ember/plum/mint; patchfox sunset/arctic/midnight/rose; nullgeist lavender/spectral_teal/crimson/slate.

## launch-002 (current): 16-bit pixel art
- Prompt core: "16-bit SNES-era pixel art game sprite … chunky visible square pixels, crisp 1-pixel dark navy outline, limited 16-color palette, 2-3 step flat shading ramps, no anti-aliasing, strictly front-facing, centered … flat #00FF00 background". The matching launch-001 image is passed as a reference.
- Native grid: 128×128, upscaled ×4 to 512 with nearest neighbour. Baseline at native y=112. Attach point at native (64,64).
- Palettes: 20–24 colours per species, 6–12 per item. One shared outline #141a33. Binary alpha only. No dithering gradients.
- Variants: colour-index swaps only. Eyes, whites and creams, Patchfox's patch, Byteblob's belly and Nullgeist's cyan eyes are protected.
- Files: `assets/px/**`, `assets/manifest.launch-002.json`, `assets/art_ext.launch-002.json`, `scripts/asset_pixel*.py`. launch-001 is kept unchanged.

## launch-003 (current): chunky low-res handheld pixel art
- Native 32×32 grid, upscaled ×16 with nearest neighbour. Bodies are 22–23 px tall, with the baseline at native row 28. Attach point is at native (16,16).
- 8–12 colours per species and 3–5 per item. One shared outline colour, #100e1c. Binary alpha. Flat 2–3 tone shading.
- 10 species: Byteblob, Patchfox, Nullgeist, Kernelcrab, Cachebat, Stacktoise, Daemowl, Shellsnail, Regexopus, Firewyrm. Original three: Byteblob is a boxy visor-face robot-slime. Patchfox is a standing fox with giant ears and a blue chest patch. Nullgeist is a hooded zigzag-hem ghost with mismatched eyes.
- Palette variants are colour-index swaps. Eyes, the visor, Patchfox's patch and Nullgeist's cyan and X eyes are locked.
- Files: `assets/px3/**`, `assets/manifest.launch-003.json`, `assets/art_ext.launch-003.json`, `assets/npcs.json`, `scripts/asset_px3*.py`.
- NPCs (cameos only): native **128×128**, factor 4 (512 display). Clawpocalypse cine v3 portraits fitted directly. Pets stay on the 32 grid.
- Cosmetics: hand-authored via `scripts/draw_cosmetics.py` at 32px; compose via `asset_px3_compose.py` with per-species transforms.
