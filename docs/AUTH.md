# Authentication and pairing

Hermagotchi uses device pairing with short-lived user codes. Raw access,
refresh and device codes are only ever returned to the client; the server
stores SHA-256 digests.

## Auth mode

`HERMAGOTCHI_AUTH_MODE` selects `dev` (the code default) or `production`.
Production deployments MUST set:

```sh
HERMAGOTCHI_AUTH_MODE=production
```

In `production`, `X-Account-Id` is ignored and only a valid session access
token is accepted. In `dev`, the historical `X-Account-Id` stub remains
available for local development and tests.

For public pairing, leave any reverse-proxy bearer gate OFF for
`/v1/auth/pair/*` routes so a new device can complete pairing. Bind the API to
loopback only and terminate TLS at nginx (or another trusted reverse proxy).

## Signup limits

Self-registration through `POST /v1/auth/pair/start` with
`new_account=true` is capped. Limits are persisted in SQLite, not kept in
process memory.

| Variable | Default | Meaning |
| --- | --- | --- |
| `HERMAGOTCHI_SIGNUP_CAP` | `100` | Maximum total account rows. |
| `HERMAGOTCHI_SIGNUP_PER_IP` | `5` | Maximum accounts created per client IP, lifetime. |

The cap is checked when pairing starts and again when the account is created
during `POST /v1/auth/pair/token`, closing races between concurrent pairings.

Failures return HTTP `403`:

- `signup_closed` - the global account cap has been reached.
- `signup_ip_limit` - this network has reached the per-IP new-account limit.

## Client IPs behind a proxy

By default the client IP is `request.client.host`. Forwarding headers are
ignored unless `HERMAGOTCHI_TRUSTED_PROXY` is explicitly set to a truthy value
(`1`, `true` or `yes`):

```sh
HERMAGOTCHI_TRUSTED_PROXY=1
```

When enabled, the left-most `X-Forwarded-For` hop is used, falling back to
`X-Real-IP`. Only enable this behind a trusted proxy that sanitizes those
headers; otherwise a client could forge its IP.
