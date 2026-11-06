# Pet animation contract (desktop)

Pane bees own `desktop/src/ui/*`. This folder is the **standalone animation
player contract** they consume — do not move UI here.

- `petAnimContract.json` — states, fps/loop defaults, how to resolve a clip id
- `petAnimPlayer.js` — tiny helper: pick clip by `{species, palette, state}`,
  advance frames, expose current `anchorDelta` for cosmetic parenting

Screens map pet/battle state → animation state via the table in
`docs/CONTRACTS.md` § Pet animation.
