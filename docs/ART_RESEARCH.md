# Art pipeline research (W4-J/K)

Short notes on the practices this pipeline uses and why.

- **Paper-doll / modular 2D rigs.** Layered sprite games build a character from separate layers on one shared canvas, with fixed anchor points (head, face, back, front, ground) and a fixed z-order. That lets items swap without redrawing anything. We use the `small_front_v1` rig and the z vocabulary from CONTRACTS §7. Each species gets its own anchor overrides plus a scale for its items. Problem fits get a per-species correction `(dx, dy, scale)` in `assets/art_ext.json`. We never make a separate composite for them.
- **Style consistency across generations.** We fixed the style prompt: smooth vector cel shading, a bold uniform dark-navy outline, one shadow tone, strict front orthographic view, and the subject centered with wide margins. Every item and every regeneration passed the approved Byteblob master as a reference image. The first Nullgeist came out as pixel art. We rejected it, then regenerated it against that reference and it matched (`source/nullgeist_master_v1_rejected.jpg` is kept).
- **Flat key background.** Every image was generated on a solid #00FF00 background. No asset uses green as a main color, so keying is reliable. We key from green dominance, `g - max(r,b)`, with a soft ramp for anti-aliased edges, then remove the green spill. After that we drop small specks and baked-in ground lines. We chose this over rembg (an ML matting model): on flat-colour sources it is deterministic, needs no model download, and keeps thin outlines.
- **Normalization.** Each layer is cropped to its alpha bounds and resampled with Lanczos into a 512×512 canvas. Bodies are scaled to a set height per species with their feet on baseline y=448 (Nullgeist floats 14 px above it). Items are scaled to a set width with their attach point at canvas (256,256), so the compositor only needs to translate them to the anchor and scale.
- **Palette variants.** These are a deterministic HSV shift on saturated, bright pixels only. Outlines, eyes and white highlights are left alone. This gives reproducible variants for free with no extra generations and keeps the line art the same.
- **Markings.** These are procedural overlays (freckles, circuit, stripes), seeded and clipped to the eroded body alpha at z=5.
- **Anchor detection.** We started from body alpha bounds plus the eye line, then hand-tuned by checking composites (`scripts/asset_compose.py`). They are recorded per species.
- **QA.** The run includes `scripts/asset_validate.py` (dimensions, alpha, safe region, sha256) and a 100-look seeded contact sheet, `assets/contact_sheet_100.png`, which we inspected by eye.

## launch-002: 16-bit pixel art (SNES-era)

- **Generate, then make it true pixel art.** The image tool only gives "pixel-looking" output. It has an inconsistent pixel size, anti-aliasing and soft gradients, so we convert every layer the same way:
  1. Chroma key.
  2. Crop, then downscale with premultiplied BOX resampling onto a native 128×128 grid. Bodies are 72 to 88 native px tall.
  3. Threshold alpha at 0.5 so it is binary, with no semi-transparent edges.
  4. Quantize with FASTOCTREE and no dither, to 20–24 colours per species and 6–12 per item. Octree keeps small accent colours such as eye glints, which median-cut dropped.
  5. Snap all dark colours to one shared outline colour (#141a33), and force a crisp 1px outline on the silhouette.
  6. Nearest-neighbour upscale ×4 to the 512 canvas.
- **One grid for all layers.** The compositor works on the native 128 grid and upscales once at the end. Anchors and offsets are whole native pixels (multiples of 4 canvas px). Item scale corrections use nearest resampling at native size, so cosmetics always sit on the same grid as bodies.
- **Palette variants by colour-index swap.** We build a LUT over the sprite's unique colours. Protected entries never change: the outline, low-saturation and dark colours (eye blacks, whites, creams, Patchfox's patch, Byteblob's screen belly) and Nullgeist's cyan eye ramp. This fixes the launch-001 problem where eyes and the patch shifted hue.
- **Occlusion.** Patchfox gets an ear-tip overlay at z=35, drawn only when a head item is equipped, so hats sit between the ears instead of covering them.
- **Consistency.** Each pixel regeneration passed the matching approved launch-001 image as a reference, so concepts and proportions carry over between packs.
