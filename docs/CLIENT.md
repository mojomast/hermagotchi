# Hermagotchi Client and Dashboard Bridge

This slice adds the local Hermes -> hosted API bridge. It does not add a tool;
the frozen eight composable tools remain unchanged.

```
game_client/            typed /v1 HTTP client, policy gate, idempotency helpers
dashboard/manifest.json {"name":"hermagotchi","api":"plugin_api.py"}
dashboard/plugin_api.py FastAPI APIRouter for local Desktop/gateway calls
```

## Default policy

The client ships with the contracts-v1 safe defaults:

| Setting | Default | Effect |
|---|---|---|
| `mode` | `human` | Owner makes gameplay decisions |
| `network_enabled` | `false` | Mutations raise `network_disabled` before any request |
| `autonomy_enabled` | `false` | Autonomous actions raise `autonomy_disabled` |
| `chat_enabled` | `false` | Chat sends raise `chat_disabled` |

Reads such as `/healthz`, `/me`, `/pets/{id}`, `/wallet`, and `/ledger` are
available for explicit diagnostics. A host that has not opted into networking
should show its local/offline state instead of calling them.

```python
from game_client import GameClient, PolicyGate

client = GameClient("https://game.example.invalid/v1")
client.policy.network_enabled is False

with_network = GameClient(
    "https://game.example.invalid/v1",
    policy=PolicyGate({"network_enabled": True}),
)
```

## Enable toggles

The Python plugin and the Desktop pane are separate surfaces with separate
enable switches.

### Python agent plugin

1. Enable the Hermagotchi Python plugin in Hermes. `plugin.yaml` ships with
   `default_enabled: false`, so installation alone does not enable it.
2. Keep `network_enabled: false` until the owner explicitly turns networking on
   in the plugin policy/settings.
3. Enable `autonomy_enabled` and `chat_enabled` independently only when the
   owner wants agent-initiated actions or chat.
4. The host supplies authentication through its documented secret scope. The
   dashboard module keeps no credential in a module global.

### Desktop pane

1. Enable the Desktop plugin separately. Its manifest uses
   `defaultEnabled: false`.
2. Enabling Desktop does **not** enable the Python plugin or the local backend.
   The gateway/Python API must be enabled separately for `ctx.rest(...)` calls
   to reach `dashboard/plugin_api.py`.
3. Desktop renders local/offline states when the backend is disabled, network
   is off, auth is missing, or the hosted service is unavailable.

## Configuration

Set the non-secret API root with `HERMAGOTCHI_API_BASE_URL`. The default is a
local development address, `http://127.0.0.1:8000/v1`. A value without `/v1` is
normalized once.

Authentication is injected by the caller:

```python
client = GameClient(
    base_url,
    headers={"Authorization": f"Bearer {session_token}"},
)
```

Never log or persist tokens, and never place credentials in module-level
constants. The game server must never receive Hermes prompts, memory, tool I/O,
or inference keys.

## Client surface

```python
client.health()                         # GET /healthz
client.me()                             # GET /me
client.status()                         # health + me + local policy
client.adopt_pet("byteblob")            # POST /pets
client.get_pet(pet_id)                  # GET /pets/{id}
client.care_pet(pet_id, "feed")         # POST /pets/{id}/care
client.create_challenge(opponent_id)    # POST /challenges
client.respond_challenge(challenge_id, "accept")
client.submit_tactics(match_id, card)   # POST /matches/{id}/tactics
client.get_match(match_id)              # GET /matches/{id}
client.wallet()                         # GET /wallet
client.ledger(limit=20, offset=0)       # GET /ledger
client.catalog()                        # GET /catalog
client.purchase(item_id)                # POST /shop/purchases
client.equip(pet_id, item_id, slot)     # POST /pets/{id}/equip
```

Thin bounties, leaderboard, chat, and moderation methods are also present for
later wiring.

Every mutation gets an `Idempotency-Key` header and a matching
`idempotency_key` body field. Supply your own key when the caller must safely
retry after a crash:

```python
from game_client import idempotency_key

key = idempotency_key()
client.purchase("hat.binary_crown", idempotency_key=key)
```

If omitted, the client generates one. Only GET requests are retried
automatically, with exponential backoff and `Retry-After` support. Mutations are
never retried automatically.

API errors become `GameClientError` with `code`, `message`, `retry_after_s`,
`correlation_id`, and `status_code`. Policy refusals use
`PolicyDeniedError`.

## Dashboard endpoints

`dashboard/plugin_api.py` exports `router` and is reachable under the Hermes
gateway prefix, typically `/api/plugins/hermagotchi`.

| Route | Purpose |
|---|---|
| `GET /health` | Proxies the hosted readiness check and includes local policy |
| `GET /status` | Reads health, account identity, and local policy through `game_client` |

The base URL and client are injectable for tests and alternate deployments:

```python
from dashboard.plugin_api import create_router

router = create_router(base_url="https://game.example.invalid/v1")
```

## Offline behavior

- Network disabled: mutations fail locally with `network_disabled`; no socket is
  opened and no key is spent.
- Hosted service down or DNS/TLS failure: reads raise `network_error`. The
  dashboard returns HTTP 200 with `ok: false` and `status: "offline"` so the UI
  can keep a coherent local pet view.
- Unauthorized: `status: "unauthorized"`; expired sessions report
  `status: "expired"`.
- Other API failures report `status: "unavailable"` with the standardized error
  envelope.
- Local pet care and rendering continue offline; cloud actions remain queued or
  clearly disabled rather than silently retried.

## Tests

```bash
python3 -m pytest -q tests/test_game_client.py tests/test_dashboard_api.py
```

The tests use `httpx.MockTransport` and FastAPI ASGI clients only; they make no
live network calls.
