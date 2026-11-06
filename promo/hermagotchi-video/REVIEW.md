# Review — Hermagotchi Television

## Delivered files

- `previews/hermagotchi-draft-720p.mp4`: **25,865,951 bytes**, H.264/AAC, **1280×720, 60 fps, 5,520 video frames, 92.000 s video duration**. AAC packet padding makes the MP4 container 92.010 s.
- Eight scene PNGs extracted from the delivered video. Combined `previews/` size: **31.71 MB**, under the 40 MB limit.
- Full-resolution HyperFrames render completed successfully; its 1080p master is ignored in `out/`.

## Visual review

Reviewed HyperFrames snapshots across all eight channels, plus the 42–46 s shop before/after, arena cards, quarter-speed replay, KO, channel-change static and the closing horizontal collapse.

- All ten species appear together in the weather map and dressed for the sign-off.
- Ten palettes are distinct; 30 manifest-sourced cosmetics appear in two shop groups and the closing lineup.
- All four NPCs appear with source portraits and verbatim quotes.
- The shop's Bits price comes from the catalog (Binary Crown: 2,000); the price starburst was moved clear of the station bug during review.
- Missing media remains visibly labeled inside the treatment. Placeholder ratings, XP, Bits and chat are not presented as game evidence.
- The HP bars, combat animation and KO are labeled illustrations. Source-footage replay has a separate quarter-speed time map.
- The graphics, pixel scale, warm palette, period typography and treatment are deliberately different from the earlier Eye Of Hermes film.

## Automated gates

- HyperFrames 0.9.19 lint: **0 errors, 0 warnings**.
- Full HyperFrames check: **passed**. No runtime errors, no layout issues, no craft errors or warnings. Software WebGL emitted readback-performance warnings. Two audio warnings identify the deliberately silent VO/music dummies.
- Canvas text is not measured by HyperFrames' DOM contrast audit (0 text samples); legibility was reviewed in rendered snapshots instead.
- `node scripts/seek-check.mjs`: nine scene/shader frames match exactly after shuffled seeks; animated time and the global intensity control both change output pixels; no page errors.
- `npm run verify`: asset coverage, contiguous timing, slot files, actual preview frame count/resolution/duration, eight stills and the combined <40 MB preview budget.
- Provenance check: all 96 copied source files match the read-only checkout byte-for-byte; all four NPC quotes match their documented source context/index.

## Production inputs still required

Six authentic image/video captures, final recorded narration, optional licensed music and final CTA copy. Verified player/rating/chat/stat text can be substituted in `copy.json`. The supplied branch documents hosting as open/not deployed; update that claim only when real evidence changes.

The requested cut runs 92 seconds. If the final submission portal enforces the source demo guide's under-90-second target, retime the sign-on/sign-off before delivery.
