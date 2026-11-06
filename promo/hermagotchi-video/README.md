# Hermagotchi Television

A **92-second, 1920×1080, 60 fps** HyperFrames submission scaffold designed as a worn late-night cable broadcast. Eight channels move from test bars through weather, home video, an infomercial, fight night, public access and an educational film, ending in a CRT collapse.

**HyperFrames 0.9.19**, pinned in `package.json` and `package-lock.json`, was the latest npm release checked on **2026-11-06**. The implementation uses the current awaited **frame-source API**, separate scene modules, and a full-frame **WebGL2 CRT/VHS shader**. It requires no image-generation service, experimental HTML-in-Canvas API, remote font loading or account login.

## Preview / check / render

This project is published under `promo/hermagotchi-video/` on branch `promo/hermagotchi-video` in `mojomast/hermagotchi`. Run the commands below **from this folder**. The committed draft and eight scene PNGs are in `previews/`; game source files are outside this video's change.

Prerequisites: Node.js 22+, npm, Python 3 with Pillow, FFmpeg/ffprobe, and HyperFrames' Chromium browser. Install Pillow with `python3 -m pip install -r requirements.txt` in your preferred virtual environment.

```sh
npm ci
npm run build
npm run preview                 # persistent local Studio, port 4333
npx hyperframes preview .build --status
npm run lint
npm run check
npm run render                  # 1080p temporary master → budgeted 720p preview
npm run stills                  # eight PNGs from the delivered preview
npm run verify                  # asset/timing/slot/budget assertions
node scripts/seek-check.mjs      # exact pixel equality after shuffled seeks
```

Open the local Studio address printed by the preview command. You can inspect the eight-channel timeline there. The canvas graphics are edited through `copy.json`, `cast.json`, `settings.json`, and the scene modules; they are not individual draggable DOM layers. `.build/` is disposable: make lasting changes in source, then rebuild. Stop the server with `npx hyperframes preview .build --stop`.

The render wrapper executes:

```sh
npx hyperframes render .build --fps 60 --quality draft --workers 2 --output out/hermagotchi-master.mp4
ffmpeg -i out/hermagotchi-master.mp4 -vf scale=1280:720:flags=lanczos \
  -c:v libx264 -preset medium -b:v 2300k -maxrate 2600k -bufsize 5200k \
  -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart \
  previews/hermagotchi-draft-720p.mp4
```

The temporary full-resolution master and generated project are gitignored. Only the compact preview and eight 720p keyframes belong in `previews/`. The wrapper enforces a 36 MB video budget, leaving room for PNGs. On environments with a broken npm global-prefix setting, prefix npm commands with `npm_config_prefix=/tmp/opencode/npm-global`.

## Swap production inputs

Replace a file under `slots/`, or edit `slots/TEXT_CTA.json`, and rebuild. **[SLOTS.md](SLOTS.md)** describes exact filenames, visible time windows, source trims and formats. **[VO_SCRIPT.md](VO_SCRIPT.md)** is a timed **draft**, with a distinct announcer direction for each channel. Voice and music dummies are silent; the current cut includes original synthesized station jingles, test tone, tuning noise and fight bells.

All authored broadcast copy is centralized in `copy.json`; the CTA is its explicitly swappable JSON slot. Species and item labels/prices there come from the source catalog. NPC quotes are verbatim and include context/index provenance. `BEATS.json` is the cut sheet, with absolute scene boundaries and review timestamps. `cast.json` assigns species, palettes and three-item loadouts.

## Effect intensity and determinism

Set **`effectIntensity` in `settings.json`** to **0** for a clean picture, **0.7** for the authored treatment or **1** for stronger CRT/VHS wear. Rebuild. The editorial tuning bursts and power-on/off remain part of the shot design. Voice/music/effects gains are in the same file.

- `effects/crt.js`: full-frame curvature, RGB phosphor mask, scanlines, highlight bloom and spatial ghosting.
- `effects/vhs.js`: seeded tracking wobble, chroma/line wear, head-switching noise and rolling hum bar.
- `effects/static.js`: frame-seeded channel transitions.
- `effects/osd.js`: CH / PLAY / REC and the fictional 02:00 tape timestamp, derived solely from timeline time.
- `shared/pets.js`: **steps(4, end)** sampling in canvas. Existing three-frame strips are padded with a held last frame during build. No interpolated sprite frames or fractional sprite scaling. Positions are snapped to source pixels; all ten pets use integer multiples of the original 32×32 grid.
- Cosmetics use manifest rig anchors plus per-species overrides, offsets, scale and z-order, including per-frame `anchor_delta`. They are never placed by eye. Item coordinates are quantized to the native grid before integer upscaling.
- `shared/runtime.js`: registers one frame source per HyperFrames sub-composition; `ready` waits for local assets/fonts; async `render(t)` waits for clip-frame decode. Every frame can be sought independently; no wall-clock timers, animation loops, network fetches, accumulated simulation state or unseeded randomness.
- Imported MP4s are decoded by FFmpeg to a cached 60 fps source sequence. The quarter-speed battle replay uses the same decoded source frames. Pictures pass through the same shader as the sprites and type.

The 720p preview downsamples the finished CRT picture; the 1080p composition's native-grid sprite placement is the reference for integer scaling. Canvas text is not covered by HyperFrames' DOM contrast/layout audit, so keyframes require visual review.

## Channel / asset rundown

Loadout identifiers **A–J** below are reused across channels; each references the exact `cast.json` entry.

| Time | Channel / source | Species, palette, items and NPCs |
|---|---|---|
| 0–6 | Sign-on / `scenes/01-sign-on.js` | Source pixel wordmark, SMPTE-style bars; no pets or NPCs. |
| 6–18 | CH 03 Pet Forecast / `02-forecast.js` | **A–J**, all 10 species and 10 distinct palettes; all six source animation states cycle as forecast fronts. No cosmetics or NPCs. |
| 18–30 | CH 05 Home / `03-home.js` | **A**, Byteblob/teal; happy → eat → sleep; no cosmetics. Habitat screenshot on an inner TV. |
| 30–46 | CH 09 Drip Shop / `04-shop.js` | **A–F** at 30–38, **G–J** at 38–42, **A** before/after at 42–46. **All 30 cosmetics** snap into their manifest anchors. **Don Piedro** portrait and real quote. |
| 46–64 | CH 12 Arena / `05-arena.js` | **D/J**, Kernelcrab/scarlet and Firewyrm/indigo, their six cosmetics. Idle cards, attack/hurt demonstration, quarter-speed replay, telestrator and illustrated KO. **Southpaw** portrait and real quote. |
| 64–76 | CH 21 Lobby / `06-lobby.js` | **Nous Girl** and **Teknium** portraits and real lines. Chat/standings capture slots, placeholder caller captions and ticker. No pets. |
| 76–85 | CH 33 Educational film / `07-how-it-works.js` | **A**, Byteblob/teal/happy, no cosmetics; four-node system diagram. |
| 85–92 | Sign-off / `08-sign-off.js` | **A–J**, all 30 cosmetics, all happy; source wordmark, CTA, bars and CRT collapse. |

| Cast | Species / palette | Cosmetics (manifest IDs) |
|---|---|---|
| A | byteblob / teal | `hat.binary_crown`, `face.pixel_shades`, `back.circuit_wings` |
| B | patchfox / rust | `hat.propeller_beanie`, `face.gold_monocle`, `front.cozy_scarf` |
| C | nullgeist / violet | `hat.syntax_wizard`, `face.noir_shades`, `front.coffee_mug` |
| D | kernelcrab / scarlet | `hat.kernel_helm`, `face.scan_visor`, `back.tiny_jetpack` |
| E | cachebat / ice | `hat.packet_cap`, `face.hex_specs`, `front.bow_tie` |
| F | stacktoise / olive | `hat.cron_crown`, `face.laser_focus`, `back.circuit_cape` |
| G | daemowl / rose | `hat.lambda_tiara`, `face.regex_rims`, `front.banana_phone` |
| H | shellsnail / sky | `hat.sudo_cap`, `face.privacy_mask`, `back.battery_pack` |
| I | regexopus / aqua | `hat.git_bandana`, `face.telemetry_lens`, `front.rubber_duck` |
| J | firewyrm / indigo | `hat.wizard_hat`, `face.oauth_eyepatch`, `front.usb_sword` |

## Source and provenance

The video was authored in a separate Git repository using a read-only `hermagotchi-src` checkout, then published here as a video-only folder. `SOURCE.json` records the exact asset-source branch and commit; the copied assets keep normal builds self-contained. `ASSETS_USED.md` lists every copied source asset and checksum, data provenance and font licenses. `scripts/prepare-assets.py` is the original one-time import utility, not part of normal builds; it expects that original sibling checkout layout and intentionally regenerates default copy/slates, so do not rerun it over production input.

Feature wording follows the captured branch's README/docs: **10 species, 81 cosmetics, eight tools, deterministic battles, opt-in social/network features**. Hosting is documented there as **open/not deployed**. The illustrated HP bars and KO are labeled animation; player ratings, rewards and chat remain placeholders. The requested 92-second plan is followed; the source's older demo guide targets under 90 seconds, so confirm the submission time limit before final export.

## Documentation consulted

Current HyperFrames README, quickstart, frame sources, HTML-in-Canvas, CLI/local render docs and bundled 0.9.19 authoring references, checked 2026-11-06:

- <https://github.com/heygen-com/hyperframes>
- <https://hyperframes.heygen.com/quickstart>
- <https://hyperframes.heygen.com/guides/frame-sources>
- <https://hyperframes.heygen.com/guides/rendering>

See `REVIEW.md` for final validation and unfinished production inputs.
