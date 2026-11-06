# Production slots

All nine slots ship with a labeled dummy or a documented silent audio placeholder. **Replace the named file (or CTA JSON value), then run `npm run build`.** No scene-code edit is needed. Keep the filename and format. The entire composition—including these slots—passes through the same CRT/VHS pipeline.

Times below are absolute film time, end-exclusive. All visual sources should be SDR/sRGB or Rec.709. Prefer large UI text and 16:9 captures. Source clips are decoded at 60 fps and contained without cropping; non-16:9 input is letterboxed. Capture details smaller than ~28 source pixels will be hard to read in a small inset, so record a focused pane/action.

| Slot | Scene / channel | Film time visible | Filename | Format / resolution | Duration | What to show |
|---|---|---|---|---|---|---|
| SHOT_PANE_HOME | 03 Home / CH 05 | 00:18–00:30 | `slots/SHOT_PANE_HOME.png` | PNG, ideally 1920×1080; dummy 1280×720 | Holds 12 s | Actual Habitat pane: adopted pet, care controls and real state. Appears on a woodgrain television inside the broadcast. |
| CLIP_SHOP_GRID | 04 Shop / CH 09 | 00:42–00:46 | `slots/CLIP_SHOP_GRID.mp4` | H.264 MP4, 1920×1080, 60 fps preferred | Supply 16 s | Real catalog, buy/equip flow and inventory confirmation. The visible window uses **source 12–16 s**; place the payoff there. A shorter clip holds its last frame. |
| CLIP_BATTLE_LIVE | 05 Arena / CH 12 | 00:50–01:01 | `slots/CLIP_BATTLE_LIVE.mp4` | H.264 MP4, 1920×1080, 60 fps preferred | Supply 18 s | Authentic battle, tactics and replay. Source 4–9 s plays at film 50–55; source 4–5 s is replayed at quarter speed at film 55–59; source 13–15 s plays at film 59–61. Match type must be visible. |
| SHOT_BATTLE_RESULT | 05 Arena / CH 12 | 01:01–01:04 | `slots/SHOT_BATTLE_RESULT.png` | PNG, 1920×1080 preferred | Holds 3 s | Actual result and practice/ranked status. Include verified rewards/rating only if present. The big KO and HP graphics remain explicitly illustrative. |
| SHOT_LEADERBOARD | 06 Lobby / CH 21 | 01:04–01:16 | `slots/SHOT_LEADERBOARD.png` | PNG, 1920×1080 preferred | Holds 12 s | Real standings, clearly scoped to the captured environment. Replace `copy.json → lobby.rows` separately with verified values if desired. |
| SHOT_CHAT | 06 Lobby / CH 21 | 01:04–01:16 | `slots/SHOT_CHAT.png` | PNG, 1920×1080 preferred | Holds 12 s | Actual opted-in chat, or its disabled state. Caller captions are editable in `copy.json → lobby.callers`; do not invent player quotes. |
| VO_MAIN | Across channels | 00:02–01:30 | `slots/VO_MAIN.wav` | PCM WAV, 48 kHz mono/stereo recommended; dummy 8 kHz mono | 88 s | Finished narration from `VO_SCRIPT.md`, aligned to absolute time minus 2 s. Dummy is silent. |
| MUSIC_BED | Global, optional | 00:00–01:32 | `slots/MUSIC_BED.wav` | PCM WAV, 48 kHz recommended; dummy 8 kHz mono | 92 s | Optional licensed music. Dummy is silent; original station jingles and tape/arena SFX already exist in `assets/broadcast.wav`. |
| TEXT_CTA | 08 Sign-off | 01:25–01:30.4 | `slots/TEXT_CTA.json` | JSON object with `text` string | Holds 5.4 s | Final short call to action. Aim for ≤55 characters. No private addresses or credentials. |

## Replacement behavior

- `npm run build` decodes MP4s into ignored `.build/assets/slot-frames/` JPEGs; frame selection is deterministic and asynchronous decoding is awaited by HyperFrames. Clip audio is intentionally excluded from these visual inserts; use VO/music for the soundtrack.
- The original source files stay untouched. Video cache invalidation uses size and modification time; deleting only `.build/assets/slot-frames/` forces re-decoding.
- PNGs are copied fresh on every build. Both image and clip slots use contain-fit, then the shader adds curvature, scanlines, RGB mask, bloom, tape jitter and chroma bleed.
- Use `settings.json → effectIntensity` to check legibility: 0 = clean, 0.7 = authored default, 1 = stronger wear. Channel-change static remains an editorial transition.
- The placeholder render does **not** constitute footage of a live server. The source README states hosting is open. Keep disclosures aligned with evidence when replacing assets.
