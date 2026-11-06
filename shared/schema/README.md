# contracts-v1 shared schemas

Frozen wire contracts for the Hermagotchi plugin, dashboard and hosted API.
`manifest.json` lists every schema with a minimal valid fixture.

- Version key: `contracts-v1`
- Economy: `economy-1`
- Combat ruleset: `battle-1`
- Asset pack placeholder: `launch-001`

Names are frozen: PetPublic, PetPrivate, Appearance, Item, Wallet, LedgerEntry,
Challenge, TacticCard, Match, ReplayEvent, ChatMessage, Goal, Policy, ApiError,
GameEvent, AssetManifest.

Validate with `python3 -m pytest -q server/tests/test_health.py`.
