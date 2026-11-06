# Hermagotchi Television — production specification

- Master: 1920×1080, 60 fps, 92 seconds (5,520 frames), SDR.
- Deliverable: 1280×720, 60 fps, H.264/AAC preview plus eight PNGs; combined `previews/` budget <40,000,000 bytes.
- Film grammar: eight channels, channel OSD, short static bursts at cuts; 2 AM tape counter is a fictional elapsed-time graphic, never the machine clock.
- Typography: bundled Anton broadcast display / VT323 character generator; titles 64–112 px, reading text usually 31–46 px. Pixel wordmark from the game.
- Palette: burgundy/cream weather, olive home video, purple/yellow infomercial, red/indigo boxing, teal public access, parchment educational film.
- Motion: four discrete sprite states per cycle; no sprite interpolation; 32px native grid with integer destination multipliers. Light tracking and noise do not affect animation timing.
- CRT: WebGL2 full-frame texture pass, curvature coefficient 0.043 × intensity, RGB split 1.5 source pixels × intensity, two-line scan period, mild highlight bloom, spatial ghost, rolling 0.042 cycles/s hum bar.
- VHS: seeded frame/line noise, bottom 4.2% head switching, rare line dropouts, ~0.22-second channel static. No temporal feedback buffer or unseeded randomness.
- Proof: existing game assets; manifest anchors and original NPC quotations; labeled slots for all UI/media proof; no invented players, ratings, rewards or hosted status.
- Prohibited style carryover: no dark navy/cyan cinematic HUD system, orbital rings, glass cards, dot-grid background, continuous sprite zooms or AI-generated artwork.
- Scene boundaries and internal cuts: `BEATS.json`. Source modules: `scenes/01-*.js` through `08-*.js`.
