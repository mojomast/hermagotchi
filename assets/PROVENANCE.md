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
