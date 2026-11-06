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

### NPCs (launch-003) — recognizable pass, 2026-11-05
Kyle asked to make the Nous characters more recognizable and to raise NPC native resolution slightly (pets stay 32px). Regenerated with `GenerateImage` using **Clawpocalypse title-screen cutouts** as reference images (`assets/cine/title/{don_piedro,nous_girl,teknium,turbofit}.png`) plus matching cinematic intro evidence panels — **not** `assets/heroes/portraits/` and **not** in-game hero sprites. Pipeline: flat green bg, green key, palette-first mode downscale, binary alpha, nearest upscale. NPC native grid is **48×48** (factor 10 → 480 display); pets remain 32×32. Palette budget raised a bit (portrait ~24 colours, bust ~16). Southpaw is still id `npc.southpaw`; visual reference is the Turbofit title cutout. 8 generations total this pass (4 early sprite-ref attempts discarded; 4 title/cine refs kept as v3). Cameos are fictional game characters; flavor lines make no claims about any real person.

| Output | Source | Reference |
|---|---|---|
| px3/npcs/don_piedro_portrait.png, don_piedro_idle_{0,1}.png | source/px3_npc_don_piedro_v3.jpg | cine/title/don_piedro.png |
| px3/npcs/nous_girl_* | source/px3_npc_nous_girl_v3.jpg | cine/title/nous_girl.png |
| px3/npcs/teknium_* | source/px3_npc_teknium_v3.jpg | cine/title/teknium.png |
| px3/npcs/southpaw_* | source/px3_npc_southpaw_v3.jpg | cine/title/turbofit.png (Southpaw) |

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
