# Task: redeploy Hermagotchi game API at a pinned tip SHA

You are redeploying the hosted Hermagotchi game API on this VPS.
Domain: hermagotchi.rizz.click (API typically at api.hermagotchi.rizz.click).
DNS for it, including a wildcard (*.hermagotchi.rizz.click), is served from this same host.

## Ground rules
- Never print, log, echo, or commit secrets (tokens, passwords, keys, bearer values). Refer to them by file path or env var **name** only.
- Ask the owner before anything destructive or irreversible: deleting app data, changing firewall/SSH, or rebooting.
- Do **not** free disk space yourself (no apt clean, journal vacuum, docker/pip cache wipes, or deleting old backups). The owner handles disk cleanup.
- Don't modify application source beyond `git fetch` + checkout of the pinned SHA.
- Keep a log of every change at `/root/hermagotchi-deploy-notes.md` (no secret values). If that notes file is missing, discover the checkout path, env file, DB path, and service name from the `hermagotchi.service` systemd unit (`systemctl cat hermagotchi` / `WorkingDirectory=` / `EnvironmentFile=`) and from nginx site config instead of guessing.

## Pin
- Repo: https://github.com/mojomast/hermagotchi (public)
- Branch: `feat/hackathon`
- **Deploy tip SHA (full):** `615a3f929769dd0927c14127611abca4e7c143f6`
- Prior rollback SHA: `1fec02f` (full `1fec02f8c518a5b2e59371be6c2f9e24ac32ebc0`) — previous W11 tip; use the full SHA recorded in prior deploy notes if available.

## Preflight: free disk space (check only)
1. Run `df -h /` and `df -h /var` (and the filesystem that holds `/opt/hermagotchi` and `/var/lib/hermagotchi` if different).
2. If any of those filesystems has **under ~2 GB free**, **STOP**. Do not fetch, migrate, or restart. Report the `df` output to the owner and wait.
3. Do not attempt cleanup. The owner frees space separately.

## What the app is
- Python FastAPI factory: `server.app.main:create_app` (uvicorn `--factory`).
- SQLite path from env `HERMAGOTCHI_DB` (production: `/var/lib/hermagotchi/hermagotchi.db`).
- Health: `GET /healthz` (also `/health` if routed). Docs: `/v1/docs`, `/v1/openapi.json`.
- Code install root: `/opt/hermagotchi`. Env file: `/etc/hermagotchi/env` (root:hermagotchi, mode 0640).
- systemd unit: `hermagotchi.service` — uvicorn on **127.0.0.1:8787** only, with `--proxy-headers --forwarded-allow-ips 127.0.0.1`.

## Auth / signup env (names only)
Ensure `/etc/hermagotchi/env` includes (create or edit; do not echo secret values):
- `HERMAGOTCHI_AUTH_MODE=production`  (code default remains `dev` for local tests; VPS must override)
- `HERMAGOTCHI_SIGNUP_CAP=100`
- `HERMAGOTCHI_SIGNUP_PER_IP=5`
- `HERMAGOTCHI_TRUSTED_PROXY=1`  (so the app trusts `X-Forwarded-For` / `X-Real-IP` from nginx only)
- Existing `HERMAGOTCHI_DB=...` and any other prior vars stay as-is unless the owner says otherwise.

### Proxy bearer gate (pairing)
Production device-pairing auth is in-tree. **Recommend keeping any reverse-proxy bearer/basic gate OFF for public `/v1/auth/pair/*` routes** so first-device pairing and approve/token exchange work from the Hermes pane. Uvicorn must stay localhost-only; TLS terminates at nginx. If a host-wide bearer gate already wraps the whole API, either:
- exempt `/v1/auth/pair/start`, `/v1/auth/pair/token`, `/v1/auth/pair/approve`, `/v1/auth/refresh`, and `/healthz`, or
- stop and ask the owner before changing the gate.
Do not invent new gate credentials in chat.

### nginx client IP
Ensure nginx passes the real client IP to uvicorn, for example:
- `proxy_set_header X-Real-IP $remote_addr;`
- `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`
- `proxy_set_header X-Forwarded-Proto $scheme;`
Reload nginx only if you change its config; verify with a dry config test first.

## Redeploy steps
1. **df check** (see Preflight). Stop if under ~2 GB free.
2. **Backup DB first** (before any code/migration change):
   ```bash
   mkdir -p /var/backups/hermagotchi
   chmod 0700 /var/backups/hermagotchi
   # use the live DB path from HERMAGOTCHI_DB
   sqlite3 /var/lib/hermagotchi/hermagotchi.db ".backup '/var/backups/hermagotchi/hermagotchi-$(date -u +%Y%m%dT%H%M%SZ).db'"
   ls -lh /var/backups/hermagotchi | tail
   ```
   Record the backup filename in the notes.
3. **Fetch + checkout the tip SHA** in `/opt/hermagotchi`:
   ```bash
   cd /opt/hermagotchi
   git fetch origin
   git checkout 1fec02f8c518a5b2e59371be6c2f9e24ac32ebc0
   ```
4. **Deps:** activate `/opt/hermagotchi/.venv` and `pip install -r requirements-dev.txt` (or the production requirements file the unit already uses). Prefer the same install path as the prior deploy.
5. **Migrations:** run the app's normal migration path (startup migration via create_app / documented migrate command). Do not hand-edit the DB. Forward-only only.
6. **Env:** set the auth/signup/trusted-proxy vars listed above; `systemctl daemon-reload` if the unit file changed (it usually should not).
7. **Restart:** `systemctl restart hermagotchi` then `systemctl status hermagotchi --no-pager`.
8. **Verify:**
   - `curl -fsS https://api.hermagotchi.rizz.click/healthz` → 200
   - A request with only `X-Account-Id` (no production bearer) against a protected route → **401** in production mode
   - Pairing start (`POST /v1/auth/pair/start`) works through the proxy (no gate blocking public auth routes)
   - Signup limits: with caps configured, excess `new_account` starts return error codes `signup_closed` / `signup_ip_limit` (do not spam; one probe is enough if safe)
   - `ss -tlnp` shows uvicorn only on 127.0.0.1:8787


## Auth / chat / economy env (names only; W11)
Keep the auth/signup/trusted-proxy vars above. Chat HTTP routes are mounted with the
other /v1 routers — **no new VPS env flag is required** for lobby chat to answer.
The Hermes desktop bridge still needs policy chat_enabled=true (alias
agent_chat_enabled) for the pane composer; that is a client/plugin policy, not a
server env. If a future HERMAGOTCHI_CHAT_ENABLED gate is added, document it here
before enabling (default should remain on for production once introduced).

Forward-only migration added on this tip:
- server/app/migrations/0011_starter_and_rate_limits.sql
- server/app/migrations/0012_economy_reprice_mythic.sql (epic/legendary reprice + mythic rarity)
  - one-time 300 Bit economy.starter_grant for eligible pre-existing accounts
  - auth_rate_hits / auth_rate_locks tables (approve lockout + pair/start limits durable across workers)

## W11 verification (after this tip)
After restart + migration:
1. curl -fsS https://api.hermagotchi.rizz.click/healthz → 200
2. New adopt grants 300 Bits once (economy.starter_grant); practice rewards 50 Bits (cap 3/day UTC).
3. Casual PvP updates ratings — GET /v1/leaderboard shows both participants after a resolved casual match.
4. Lobby chat: GET/POST /v1/chat/channels/lobby/messages (not /v1/chat/messages).
5. Five wrong approve attempts for the same IP or code lock across uvicorn workers (DB-backed).
6. Resolved match JSON includes winner, result, final_hp, rounds on the match object.
7. Shop thumbnails are served by the desktop asset bridge (px3/thumbs/*_thumb.png); live API has no /assets route — do not expect GET /v1/assets/... on the VPS.

## Rollback
If health checks fail or pairing is broken:
1. `systemctl stop hermagotchi`
2. Restore DB from the backup just taken (copy backup over `HERMAGOTCHI_DB` only after stopping the service).
3. `cd /opt/hermagotchi && git checkout 1fec02f8c518a5b2e59371be6c2f9e24ac32ebc0` (or the full prior SHA from notes)
4. Reinstall deps if needed, `systemctl start hermagotchi`, re-check `/healthz`
5. Report what failed and leave the new tip unchecked out until the owner decides.

## Report back
- Deployed tip SHA (full)
- Backup path used
- `df -h` summary at start
- Env var **names** confirmed (not values)
- Whether nginx X-Forwarded-For / X-Real-IP is set
- Verify results (health 200, X-Account-Id → 401, pairing start, signup limit probe)
- Anything you stopped short of
