# Changelog

All notable changes to Hermagotchi are recorded here. The `0.1.0` entry is the
hackathon release candidate on `feat/hackathon`; it is not tagged and is not
merged to `main`.

## [0.1.0] - 2026-11-06

First public release candidate. It keeps the frozen eight-tool contracts-v1
surface and adds the W7-W10 user-facing work below.

### Added

- **Device-pairing auth (W7).** Short-lived user codes plus access, refresh and
  device tokens; only SHA-256 digests are stored. The client ships a pairing
  client and owner-only session store with refresh, device listing, revoke and
  logout. The dashboard bridge exposes pair start/poll without leaking the
  device code or raw tokens to the Desktop UI.
- **Care and unequip (W8).** Idempotent `feed`, `play` and `rest` actions with
  cooldown and replay receipts, plus equipment removal that keeps the owned
  item in inventory.
- **Challenge inbox and practice (W8).** Pending challenge reads and
  deterministic practice battles against Teknium, including the daily rewarded
  practice allowance.
- **Dashboard bridge (W8).** Allowlisted reads and mutations between Hermes and
  the local server, with bearer handling kept out of the Desktop UI.
- **Local asset bridge (W9).** Manifest and asset-file serving from the plugin,
  preferring `manifest.launch-003.json`.
- **Desktop pane (W9/W10).** Six tabs: Habitat, Battle, Shop, Leaderboard, Chat
  and Settings. Explicit backend-disabled, network-off, auth-missing and
  service-unavailable states; Chat stays off until enabled.
- **launch-003 art and roster (W10).** Ten adoptable species with pixel art and
  per-palette animation strips: Byteblob, Patchfox, Nullgeist, Kernelcrab,
  Cachebat, Stacktoise, Daemowl, Shellsnail, Regexopus and Firewyrm.
- **Cosmetics and composition (W10).** 81 active shop items across head, face,
  back, front, aura, emote, habitat and title slots, with per-species
  `head`/`face`/`back`/`front`/`hand`/`ground` compose anchors so each item fits
  all ten species.
- **Signup limits (W10).** `HERMAGOTCHI_SIGNUP_CAP` (default 100) and
  `HERMAGOTCHI_SIGNUP_PER_IP` (default 5) return `403 signup_closed` or
  `403 signup_ip_limit`. `HERMAGOTCHI_TRUSTED_PROXY` enables
  `X-Forwarded-For` / `X-Real-IP` only behind a trusted proxy.

### Changed

- The runtime asset pack and shop catalog advance to `launch-003`, while
  existing pets, inventory, equipment and care rows are preserved.
- Desktop pet rendering uses the launch-003 manifest, per-species anchors and
  animation player; cosmetics no longer assume the original three species.
- `HERMAGOTCHI_AUTH_MODE` still defaults to `dev`; production deployments set
  `HERMAGOTCHI_AUTH_MODE=production` to require paired session tokens.
- README now documents the actual launch-003 build, ten species, 81 cosmetics,
  pairing auth, signup caps and the release-candidate status.

### Security

- Access, refresh and device tokens are hashed at rest, never shown in tool
  output or the Desktop UI, and the client session file is owner-only.
- Production mode ignores the legacy `X-Account-Id` header.
- Signup caps are checked both when pairing starts and when the account is
  created, closing concurrent-pairing races.
- Forwarded client-IP headers are ignored unless `HERMAGOTCHI_TRUSTED_PROXY` is
  explicitly enabled.

### Fixed

- Corrected stale README wording about the build and hosted status; the docs now
  state launch-003, all ten species and hosted deployment as optional/OPEN for
  the operator.
