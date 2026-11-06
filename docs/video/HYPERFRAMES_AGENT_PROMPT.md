# Task: build the HyperFrames project for the Hermagotchi submission video

You are preparing a **HyperFrames** (HTML-to-video) project for the Hermagotchi hackathon
submission video. You build every scene, motion and effect. A second agent will later drop
in the live footage, screenshots and voiceover, then render. Because of that, **every
missing piece has to be a clearly named placeholder slot**, never a hard-coded guess.

Repo: https://github.com/mojomast/hermagotchi. Base branch: `feat/hackathon`.
Work on a new branch, **`feat/submission-video`**, and push only that branch.
Do not merge to main, tag, force-push, rewrite history or delete anything outside `video/`.

Before you start, read the current HyperFrames docs and README for the exact CLI and
composition format (project init, preview, lint and render commands). Use whatever they
say is current, and pin the version you used in `video/README.md`.

## The pitch (what the video must land in ~90 s)
Hermagotchi is a multiplayer agent-pet plugin for Hermes. You adopt a pixel pet, it grows
alongside your agent's real work, you dress it up from an 81-item shop, and you battle
other people's pets on a live server with ratings, a leaderboard and a lobby chat. Nous
NPCs (Don Piedro, Nous Girl, Teknium, Southpaw) run the shop, lobby, practice and arena.

## Assets: use them heavily (repo paths, all committed)
- `assets/px3/anims/<species>_<palette>_<state>.png`: 40 species/palette combos x 6 states
  (idle, happy, eat, sleep, attack, hurt). Each is a **2048x512 sprite strip, 4 frames of 512x512**.
  Animate them with CSS `steps(4)` and `image-rendering: pixelated`.
- `assets/px3/species/`: the 10 species are byteblob, cachebat, daemowl, firewyrm,
  kernelcrab, nullgeist, patchfox, regexopus, shellsnail and stacktoise.
- `assets/px3/items/` (81 cosmetics) and `assets/px3/thumbs/*_thumb.png` (shop thumbs).
- `assets/px3/overlays/` holds per-species overlays such as patchfox ears. `assets/px3/markings/` and `assets/px3/palettes/` hold the rest.
- `assets/px3/npcs/<npc>_{portrait,dialog,idle_0,idle_1}.png` for the four NPCs.
- `assets/npc_lines.json`: real NPC quips. Use these verbatim for the NPC text beats.
- `assets/ui/wordmark.png` and `wordmark@2x.png`: the pixel HERMAGOTCHI wordmark.
- `assets/contact_sheet_100*.png`: contact sheets, good for a "the whole roster" wall.
- `assets/manifest.json`: the source of truth for which item fits which slot (hat, face, aura,
  back, emote and so on) and its anchor offsets. **Read it to place cosmetics correctly on pets.**
  Don't eyeball them.
- `desktop/src/ui/styles.css`: the pane's colours and fonts. Match the video's palette to it.

Rules for art: **do not generate new images or AI art**. Everything is built from the repo
assets, CSS, SVG, canvas or WebGL in code. Keep pixels crisp (no smoothing on scale-ups;
scale by integer factors).

## Scene plan (target 85-95 s at 1920x1080, 30 or 60 fps)
1. **Cold open (0-6 s):** black, CRT power-on line expanding into a scanlined screen. A
   pixel-dissolve reveal of the wordmark, then a hard cut to a single Byteblob idling.
2. **Roster burst (6-16 s):** all 10 species pop in on a grid with staggered spring easing,
   each in a different palette and state, then shuffle palettes live (swap strips on beat).
   End by pulling back into the contact-sheet wall with parallax depth.
3. **Hatch and grow (16-28 s):** one pet's happy, eat and sleep states, with stat bars
   filling. **Slot `SHOT_PANE_HOME`** (a screenshot or clip of the real pane) slides in beside it inside a
   floating device/pane frame with a soft glow and reflection.
4. **Drip montage (28-44 s):** a fast cosmetic try-on. One pet cycles hat, face, aura and back
   items from the manifest on the beat, with a whip-pan to the next pet (aim for 6+ pets and
   20+ items total). Show auras with additive-blend glow. Shop thumbs rain or orbit behind.
   **Slot `CLIP_SHOP_GRID`** for real Shop footage. Don Piedro's dialog card uses a real shop line
   from `npc_lines.json`.
5. **Battle (44-64 s):** a split-screen versus card (pet A vs pet B portraits with a diagonal
   wipe, VS slam, screen shake). Then attack and hurt strips trade blows with HP bars,
   damage numbers, hit-flash, chromatic-aberration pulses and a pixel-shatter KO. Southpaw
   announces with a real line. **Slot `CLIP_BATTLE_LIVE`** for real PvP footage, and **slot
   `SHOT_BATTLE_RESULT`** for the result screen.
6. **Social (64-76 s):** the leaderboard climbs with animated rank swaps. **Slot
   `SHOT_LEADERBOARD`**. Nous Girl hosts the lobby, with chat bubbles typing in. **Slot
   `SHOT_CHAT`**. Teknium gives a practice tip.
7. **How it works (76-86 s):** a clean diagram (Hermes, the plugin pane, the game API, other players)
   drawn with animated SVG strokes and labels. Keep it to 4-5 nodes, with no hostnames or URLs.
8. **Outro (86-92 s):** every pet decked out on a stage, lined up and bouncing, under the
   wordmark. Add **slot `TEXT_CTA`** (install line or repo link, filled in later) and a
   "built for the Hermes hackathon" tag.

## Effects to include (tasteful, cutting edge, not noisy)
- CRT scanlines plus subtle vignette as a global toggleable layer.
- Pixel-dissolve or mosaic transitions (canvas or WebGL shader), and whip-pan with motion blur.
- Chromatic aberration hit pulses, screen shake and impact frames on battle hits.
- Additive glow and particles (floating "Bits" coins, sparkles) driven by seeded randomness,
  so renders are deterministic.
- Parallax depth on the roster wall, plus kinetic typography for the 4-6 on-screen captions.
- Everything must render deterministically, so there are no wall-clock timers. Drive motion from the
  HyperFrames timeline or seek API as its docs require.

## Placeholder slots (the second agent fills these)
Create `video/slots/` with one placeholder per slot. Each is a clearly labelled dummy PNG or MP4
at the right size, with "SLOT: NAME" burned in. Then write `video/SLOTS.md` as a table of
slot name, scene, timecode, expected file name and format, resolution, duration and what it should show.
At minimum, include these slots:
- `SHOT_PANE_HOME`, `CLIP_SHOP_GRID`, `CLIP_BATTLE_LIVE`, `SHOT_BATTLE_RESULT`,
  `SHOT_LEADERBOARD` and `SHOT_CHAT` (1920x1080 or pane-sized; say which).
- `VO_MAIN` (voiceover WAV/MP3, ~85 s). Write a **draft VO script** in `video/VO_SCRIPT.md`
  with per-scene timecodes and line lengths that fit. Mark it as a draft.
- `MUSIC_BED`: optional, a silent placeholder track. Note the beat markers you cut to in
  `video/BEATS.json` (seconds), so the music can be swapped and retimed.
- `TEXT_CTA` and any caption strings: put all on-screen text in one `video/copy.json`.
Swapping a slot must only mean replacing a file or a JSON value, never editing scene code.

## Deliverables (commit under `video/` only)
- The HyperFrames project (`video/index.html` or whatever layout the docs prescribe), with
  scenes split into readable files plus shared effect modules.
- `video/README.md` covering the HyperFrames version, preview, lint and render commands, how
  to swap slots, and the expected render time.
- `video/SLOTS.md`, `video/VO_SCRIPT.md`, `video/copy.json` and `video/BEATS.json`.
- `video/previews/`: a **low-res draft render** (720p, placeholders in place) plus 8 key-frame
  PNGs, one per scene. Keep the total under 40 MB, and don't commit full-res renders.
- Reference repo assets by relative path (`../assets/...`). **Do not copy the asset folders.**

## Acceptance
- The project lints and renders cleanly with the documented command, deterministically
  (two renders of the same frame match).
- At least 10 species, 6 palettes, 20 cosmetic items and all 4 NPCs appear on screen.
  List them per scene in `video/README.md`.
- No secrets, tokens, private hostnames or tailnet URLs anywhere. Run a secret scan before
  pushing (e.g. `git diff --cached | grep -iE "token|secret|key|ts\.net"` and review the hits).
- Push `feat/submission-video` and report the branch, the tip SHA, the render command, the slot list
  and anything you couldn't finish.
