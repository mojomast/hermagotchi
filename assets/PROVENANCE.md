# Asset provenance — launch-001

- **Tool:** Grok Bot built-in image generation (GenerateImage), run by Grok Bot on Kyle Durepos's request ("generate the art yourself"), 2026-11-05. No outside paid provider was used.
- **Rights note:** original designs made for Hermagotchi. Prompts ask for original characters and name no franchise. The output was reviewed for resemblance to existing IP and none was found that we know of. Kyle can confirm the generator's license terms before a commercial release.
- **Pipeline:** `assets/source/*.jpg` (raw, never edited in place) → `scripts/asset_build.py` (chroma key, normalize, palettes, markings, manifest) → `scripts/asset_compose.py` (render_pet, contact sheet).
- Every raw output is kept, including rejected ones (`*_rejected.jpg`). 17 generations total (16 used, 1 rejected).

| Output | Source | Prompt summary |
|---|---|---|
| species/byteblob_body.png | source/byteblob_master_v1.jpg | species master: round gumdrop slime-robot, teal, cream screen belly, antenna; locked style prompt |
| species/patchfox_body.png | source/patchfox_master_v1.jpg | species master: sitting fox-like coding familiar, tall ears, curled tail, stitched cheek patch |
| species/nullgeist_body.png | source/nullgeist_master_v2.jpg | species master: floating lavender glitch ghost, wisp tail; v1 rejected (pixel-art style drift); v2 used the Byteblob reference |
| items/binary_crown.png | source/item_binary_crown_v1.jpg | accessory-only prompt + Byteblob style reference: Gold crown with magenta gem finials |
| items/propeller_beanie.png | source/item_propeller_beanie_v1.jpg | accessory-only prompt + Byteblob style reference: Red/yellow propeller beanie |
| items/syntax_wizard.png | source/item_wizard_hat_v1.jpg | accessory-only prompt + Byteblob style reference: Blue wizard hat with brace/star print |
| items/pixel_shades.png | source/item_pixel_shades_v1.jpg | accessory-only prompt + Byteblob style reference: Blocky pixel sunglasses |
| items/gold_monocle.png | source/item_monocle_v1.jpg | accessory-only prompt + Byteblob style reference: Gold monocle with chain |
| items/circuit_wings.png | source/item_circuit_wings_v1.jpg | accessory-only prompt + Byteblob style reference: Cyan circuit-board wings |
| items/tiny_jetpack.png | source/item_jetpack_v1.jpg | accessory-only prompt + Byteblob style reference: Twin-tank retro jetpack |
| items/ember_halo.png | source/item_aura_flame_v1.jpg | accessory-only prompt + Byteblob style reference: Magenta flame-wisp aura ring |
| items/data_orbit.png | source/item_aura_datacubes_v1.jpg | accessory-only prompt + Byteblob style reference: Orbit of golden data cubes |
| items/cozy_scarf.png | source/item_scarf_v1.jpg | accessory-only prompt + Byteblob style reference: Red striped knit scarf |
| items/heart_bubble.png | source/item_emote_heart_v1.jpg | accessory-only prompt + Byteblob style reference: Heart speech-bubble emote |
| items/plush_cushion.png | source/item_habitat_cushion_v1.jpg | accessory-only prompt + Byteblob style reference: Mustard tufted floor cushion |
| items/royal_ribbon.png | source/item_title_banner_v1.jpg | accessory-only prompt + Byteblob style reference: Blank purple ribbon nameplate (text drawn by client) |
| palettes/*.png, markings/*.png | derived | procedural (HSV shift / seeded overlays), no generation |

## launch-002 (16-bit pixel art), 2026-11-05
Same tool (Grok Bot built-in image generation) and the same rights note as above. Kyle asked: "i want a more pixeled 16 bit style". There were 11 new generations; each passed the matching launch-001 source as a reference image. Every layer was then converted to true pixel art by `scripts/asset_pixel_build.py`.

| Output | Source |
|---|---|
| px/species/byteblob_body.png | source/px_byteblob_v1.jpg |
| px/species/patchfox_body.png | source/px_patchfox_v1.jpg |
| px/species/nullgeist_body.png | source/px_nullgeist_v1.jpg |
| px/items/binary_crown.png | source/px_item_crown_v1.jpg |
| px/items/propeller_beanie.png | source/px_item_beanie_v1.jpg |
| px/items/syntax_wizard.png | source/px_item_wizard_v1.jpg |
| px/items/gold_monocle.png | source/px_item_monocle_v1.jpg |
| px/items/circuit_wings.png | source/px_item_wings_v1.jpg |
| px/items/tiny_jetpack.png | source/px_item_jetpack_v1.jpg |
| px/items/ember_halo.png | source/px_item_aura_flame_v1.jpg |
| px/items/cozy_scarf.png | source/px_item_scarf_v1.jpg |
| px/items/pixel_shades.png, data_orbit.png, heart_bubble.png, plush_cushion.png, royal_ribbon.png | the launch-001 sources, pixel-converted (no new generation) |
| px/palettes, px/markings, px/overlays | procedural |

## launch-003 (low-res handheld pixel art), 2026-11-05
Kyle asked: "i want them to be more pixelated. regenerate them entirely please in a different style". The tool and rights note are the same as above. All sources are new generations with no reference images, except the NPCs (below). Conversion is done by `scripts/asset_px3_build.py`. Generations: 3 species and 13 items.

| Output | Source |
|---|---|
| px3/species/{byteblob,patchfox,nullgeist}_body.png | source/px3_{byteblob,patchfox,nullgeist}_v1.jpg |
| px3/items/binary_crown, propeller_beanie, syntax_wizard, pixel_shades, gold_monocle, circuit_wings, tiny_jetpack, ember_halo, data_orbit, cozy_scarf, heart_bubble, plush_cushion, royal_ribbon | source/px3_item_{crown,beanie,wizard,shades,monocle,wings,jetpack,aura_flame,aura_orbit,scarf,emote,cushion,ribbon}_v1.jpg |
| px3/palettes, px3/markings, px3/overlays | procedural |

### NPCs (launch-003) — face readability pass, 2026-11-05
Kyle: facial features still not pronounced enough on 37f5fa0. Kept magenta key, cine Lab palettes, 128 native. Regenerated with bold-face prompts (`*_v6.jpg`, 4 gens). Pipeline: mild face unsharp, protect high-contrast face pixels during palette remap, selective face outlines, orphan cleanup, Teknium non-goggle red/warm stray removal, Don spoon thicken. Portrait + dialog + idle. Pets stay 32. **Superseded by hand-pixel pass below.**

| Output | Source | Reference (primary) |
|---|---|---|
| px3/npcs/don_piedro_{portrait,dialog,idle_*} | source/px3_npc_don_piedro_v6.jpg | cine/v3/portraits/don_piedro.png |
| px3/npcs/nous_girl_* | source/px3_npc_nous_girl_v6.jpg | cine/v3/portraits/nous_girl.png |
| px3/npcs/teknium_* | source/px3_npc_teknium_v6.jpg | cine/v3/portraits/teknium.png |
| px3/npcs/southpaw_* | source/px3_npc_southpaw_v6.jpg | cine/v3/portraits/turbofit.png |

### NPCs (launch-003) — hand-pixel from scratch, 2026-11-05
Kyle: prior painterly-then-downscale/remap results looked garbage; create brand-new NPC pixel art authored as pixel art from the start, using cine/v3/portraits as reference (Southpaw = turbofit). Abandoned Lab k-means remap pipeline. Method: GenerateImage SNES/GBA bust prompts on flat grey bg (4 gens → `*_v7.jpg`); per-character fixed hand palette (12–20 colours picked from cine refs); flat-grey edge-flood key (no low-luma key — preserves black bob/vest); palette snap; BOX onto native 128 grid; binary alpha; hole fill; selective 1px outline; light face pixel pass; fringe/orphan scrub. Contract unchanged: portrait + dialog + idle_0/1, native [128,128] factor 4. Pets stay 32. `assets/npc_lines.json` left untouched.

| Output | Source | Reference (primary) |
|---|---|---|
| px3/npcs/don_piedro_{portrait,dialog,idle_*} | source/px3_npc_don_piedro_v7.jpg | cine/v3/portraits/don_piedro.png |
| px3/npcs/nous_girl_* | source/px3_npc_nous_girl_v7.jpg | cine/v3/portraits/nous_girl.png |
| px3/npcs/teknium_* | source/px3_npc_teknium_v7.jpg | cine/v3/portraits/teknium.png |
| px3/npcs/southpaw_* | source/px3_npc_southpaw_v7.jpg | cine/v3/portraits/turbofit.png |

### NPCs (launch-003) — Kyle pixel cleanup, 2026-11-05
No new gens. Native-128 pixel edits on top of hand-pixel v7: thicker Don spoon + metallic highlight; Nous/Southpaw hair-edge fringe scrub (zero orphan tips); Teknium 2–3px smirk with shade; Southpaw solid near-black vest + clear studs; shared eye highlights, silhouette smooth, re-outline. Applied to portrait, dialog, idle_0/1. `npc_lines.json` untouched.



### NPCs (launch-003) — true from-scratch hand-author, 2026-11-05
Kyle: prior gen/snap passes were a waste of tokens; redraw from scratch with NO GenerateImage and NO v6/v7 sources. Each NPC is an explicit pixel/shape script in `scripts/draw_npcs.py` at 64×64 (named 12–16 colour palettes from cine/v3 refs by eye), nearest ×2 to native 128, ×4 display. Portrait + dialog + idle blink/bob. `lines_ref: npc_lines.json` restored. Pets stay 32.

| Output | Source | Reference (eyes only) |
|---|---|---|
| px3/npcs/don_piedro_* | scripts/draw_npcs.py#don_piedro | cine/v3/portraits/don_piedro.png |
| px3/npcs/nous_girl_* | scripts/draw_npcs.py#nous_girl | cine/v3/portraits/nous_girl.png |
| px3/npcs/teknium_* | scripts/draw_npcs.py#teknium | cine/v3/portraits/teknium.png |
| px3/npcs/southpaw_* | scripts/draw_npcs.py#southpaw | cine/v3/portraits/turbofit.png |

### launch-003 extra species (7), 2026-11-05
Kyle asked for 7 more base pets in the same style, for 10 in total. Each is one new generation with no reference image, using the same pipeline (green key, palette-first mode downscale, binary alpha, palette swaps with eyes locked). Anchors are derived automatically from each silhouette.

| Output | Source |
|---|---|
| px3/species/kernelcrab_body.png | source/px3_kernelcrab_v1.jpg |
| px3/species/cachebat_body.png | source/px3_cachebat_v1.jpg |
| px3/species/stacktoise_body.png | source/px3_stacktoise_v1.jpg |
| px3/species/daemowl_body.png | source/px3_daemowl_v1.jpg |
| px3/species/shellsnail_body.png | source/px3_shellsnail_v1.jpg |
| px3/species/regexopus_body.png | source/px3_regexopus_v1.jpg |
| px3/species/firewyrm_body.png | source/px3_firewyrm_v1.jpg |
| px3/palettes/{species}_*.png, px3/markings/{species}_*.png | procedural |

### NPCs (launch-003) — clawpocalypse cine v3 direct, 2026-11-05
Kyle: "just use the portraits from the game instead". No GenerateImage, no pixel redraw. Lanczos-fit `assets/cine/v3/portraits/{don_piedro,nous_girl,teknium,turbofit}.png` into 512 (native 128×4) portrait / dialog bust / idle (+2px bob). `lines_ref: npc_lines.json` kept. `scripts/draw_npcs.py` left in tree unused.

| Output | Source | Reference |
|---|---|---|
| px3/npcs/* | source/cine_v3_{don_piedro,nous_girl,teknium,southpaw}.png | clawpocalypse cine v3 portrait |

### Daemowl third eye, 2026-11-05
Kyle: "can you give daemowl three eyes please". Hand-pixel edit on native 32 grid of `px3/species/daemowl_body.png` — amber forehead eye with outline, pupil, highlight matching existing eyes. Palettes regenerated via `palette_swap`. Wired into `scripts/asset_px3_build.py` (`daemowl_third_eye`) so rebuilds keep it. No GenerateImage. Blink is a client transform on the base sprite (all three eyes move together).

Follow-up: filled brow notch and facial-disc pad so the third eye is embedded in feather colours with no surrounding transparent gaps (body + palettes; build script updated).

### Cosmetics pack (~60), 2026-11-05
Kyle: ~60 NEW cosmetics, hand-authored in `scripts/draw_cosmetics.py` (no GenerateImage). Categories: hats, face, neck/back, held props, auras (many 2-frame). Per-species transforms for all 10 pets; `hand` anchor for held props; daemowl face offsets clear the third eye. Shop migration `0008_cosmetics_pack.sql`. Existing 13 px3 items kept and given full per_species maps.
### Pet state animations, 2026-11-05
Kyle: simple hand-authored animations (idle/happy/eat/sleep/hurt/attack) for all 10 species × palette variants. Derived in `scripts/draw_anims.py` from existing palette sprites via pixel transforms + blink/Zz edits — no GenerateImage. Strips in `assets/px3/anims/`; metadata in manifest `animations{}` + art_ext. Desktop contract: `desktop/src/anim/`.
