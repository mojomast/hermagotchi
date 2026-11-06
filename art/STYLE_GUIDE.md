# Hermagotchi Art Style Guide (contracts-v1)

Short, practical guide for original cel-shaded indie creature art. It defines
the shared look and the rig constraints; it does not grant rights to any
third-party character or style.

## Status

The files currently under `assets/fixtures/` are **PLACEHOLDER_NOT_SHIP** solid
color shapes. They exist only to exercise the manifest, validator and renderer
plumbing. They are not final art, must not be presented as final art, and must
be replaced by reviewed original layers before a release or demo claims
finished visuals.

## Canvas and pose

- 512 x 512 RGBA PNG, transparent background, no baked text, logo, watermark,
  environment or cast shadow.
- Centered, front-facing 3/4-neutral pose. Feet/ground contact at baseline
  `y=448`; centerline `x=256`.
- Keep the silhouette inside `x=65..447`, `y=75..450` (safe region). Leave
  breathing room for headwear, ears and particles.
- Every modular layer is exported on the same canvas even when mostly empty.
  A trimmed accessory is not a rig layer; place it using anchor metadata.

## Silhouette and species

The three starter species must read differently at 96 px, not just by color:

- **Byteblob** - round modular slime/robot. Soft stacked volumes, simple gear
  anchors, defensive stance.
- **Patchfox** - fox-like coding familiar. Pointed or rounded ears, visible
  tail, nimble lean.
- **Nullgeist** - spectral glitch creature. Floating, tapered or wispy lower
  body, no planted feet required.

Do not copy franchise pets, trademark mascots, recognizable game characters or
existing sprite sheets. Do not trace or lightly recolor someone else's design.
When using reference material, keep it as mood/composition reference only and
record provenance.

## Line and shading

- Bold, coherent outline: roughly 6-8 px at 512 (about 3-4 px at 256), with
  rounded joints and slightly tapered ends.
- Use a dark tinted outline from the palette instead of pure black. Vary weight
  only for depth cues, not randomly.
- Cel shading with 2-3 flat value bands. Light comes from the upper left.
- Avoid soft photographic gradients, noisy texture, bloom and baked highlights.
- Eyes and mouth must stay readable at 96 px. Prefer simple shapes with strong
  dark/light separation.

## Palette

- Limit each creature to a cohesive palette of about 4-6 base colors plus a
  small accent.
- Check contrast in grayscale and in colorblind-safe previews.
- Cosmetics should share the same palette discipline so mixed loadouts look
  authored, not assembled from unrelated games.

## Layers, anchors and z-order

Author each attachment as a separate transparent layer with only that item's
pixels. Never paint body or skin into an equipment layer.

Equipped slots: `head`, `face`, `back`, `front`, `aura`, `emote`, `habitat`,
`title` (one item per slot).

Z-order vocabulary: `aura_back(-30)`, `shadow(-20)`, `back_attachment(-10)`,
`body(0)`, `markings(5)`, `eyes_mouth(10)`, `facewear(20)`, `headwear(30)`,
`front_attachment(40)`, `particles_front(50)`.

Anchors are normalized coordinates on the 512 canvas: `head=(0.50, 0.23)`,
`face=(0.50, 0.42)`, `back=(0.50, 0.47)`, `front=(0.50, 0.66)`,
`ground=(0.50, 0.88)`. Species may override anchors (for example a taller
Patchfox head). Headwear must follow the head anchor, never the global stage.

## QA checklist

- True transparency, clean alpha edge, no checkerboard-painted background.
- No cut-off pixels outside the safe region and no item floating off-anchor.
- One head, one face, no duplicate eyes, no accidental body repaint.
- Headwear moves with head bob; horns/ears sit correctly around it.
- Legible at 96, 160, 256 and 512 px.
- Original design, documented provenance, no third-party logos or characters.
- Manifest hashes match the exported PNG bytes; validator passes.
