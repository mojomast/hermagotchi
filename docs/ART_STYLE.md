# Hermagotchi style guide (locked for launch-001)

**Style prompt core:** "Original indie creature-game character sprite … cozy futuristic 2D cel-shaded collectible monster, bold uniform dark navy outline, flat cel shading with one shadow tone, limited palette, strictly front-facing orthographic view, full body centered, wide empty margins. Perfectly flat solid pure chroma green #00FF00 background, no gradient, no cast shadow, no ground, no props, no text, no watermark."
**Accessory prompt core:** "Match the reference art style exactly … Draw ONLY a single detachable accessory, no character: {item}, front view, centered … flat #00FF00 background." Reference: `assets/source/byteblob_master_v1.jpg`.
**Rules:** outline is navy (~#0f1a33). No green as a main colour. One shadow tone. Faces must read at 96 px. No text baked into layers (the client draws title text on the ribbon).
**Canvas:** 512×512 RGBA, baseline y=448, safe x 65..447 / y 75..450. Item attach point is at (256,256).
**Species:** Byteblob (round gumdrop slime-robot, antenna, screen belly). Patchfox (sitting fox familiar, tall ears, plume tail, stitched cheek patch). Nullgeist (floating ghost, curling wisp tail, glitch cubes). Each species has its own silhouette.
**Palettes (procedural HSV):** byteblob aqua/ember/plum/mint; patchfox sunset/arctic/midnight/rose; nullgeist lavender/spectral_teal/crimson/slate.
