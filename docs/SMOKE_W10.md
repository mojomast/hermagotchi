# Smoke Report — HGT-W10

- **Task:** HGT-W10-SMOKE (fresh-checkout smoke)
- **Date:** 2026-11-06
- **Tip SHA:** `4a683a5b571892ca1cafceb4a8f5bd442d42985d`
  (`HGT-W10: rebuild desktop/plugin.js after X/Y/Z compose+signup polish`)
- **Branch:** `feat/hackathon` (tracked from `origin/feat/hackathon`)
- **Clean clone path:** `/tmp/hermagotchi-smoke-w10` (created with `rm -rf` first; the
  existing worktree was not used)

## Environment

| Item | Value |
| --- | --- |
| Python | 3.12.3 |
| Node | v24.21.0 (>= 20 required) |
| Virtualenv | `.venv` inside the clean clone |
| fastapi | 0.162.0 |
| pytest | 9.2.0 |

## Commands & Results

| # | Check | Command | Result |
| --- | --- | --- | --- |
| 1 | Clean clone | `rm -rf /tmp/hermagotchi-smoke-w10 && git clone https://github.com/mojomast/hermagotchi /tmp/hermagotchi-smoke-w10 && git checkout -B feat/hackathon origin/feat/hackathon` | PASS |
| 2 | Venv + deps | `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt` | PASS |
| 3 | App factory | `python3 -c "from server.app.main import create_app; app=create_app(); print('app_ok', app.title if hasattr(app,'title') else type(app))"` | PASS — `app_ok Hermagotchi Game API` |
| 4 | Schema token measurement | `python3 -m pytest -q tests/test_schemas_measure.py` | PASS — 2 passed |
| 4b | o200k total | `python3 evals/measure_schemas.py --json` | PASS — **o200k = 933** (cl100k = 870) |
| 5 | Desktop build freshness | `node scripts/build_desktop.mjs --check` | PASS — `desktop/plugin.js is up to date` |
| 6 | Hermes CLI / plugin validation | `hermes plugins doctor .` / `validate` | N/A — `hermes` not on PATH; `scripts/hermes_check.sh` exited 127 (`FAIL: hermes executable not found on PATH`) |
| 7 | Targeted tests | `python3 -m pytest -q tests/test_plugin_tools.py server/tests/test_pets_adopt.py server/tests/test_signup_limits.py` | PASS — 33 passed, 1 warning |

### o200k per-tool breakdown

| Tool | o200k tokens |
| --- | --- |
| hermagotchi_battle | 81 |
| hermagotchi_challenge | 138 |
| hermagotchi_goals | 171 |
| hermagotchi_meta | 88 |
| hermagotchi_pet | 138 |
| hermagotchi_shop | 105 |
| hermagotchi_social | 109 |
| hermagotchi_status | 103 |
| **Total** | **933** |

Exactly 8 Hermes tools are present; no tools were added and `schemas.py` / `tools.py`
were not edited.

## Hermes availability

`hermes` is **not installed / not on PATH** in this environment. The fallback
`scripts/hermes_check.sh` was run and reported the same missing executable (exit 127).
The script also wrote `docs/evidence/hermes_plugins_doctor.log` and
`docs/evidence/hermes_plugins_validate.log` with that failure.

## Warning observed

`starlette.testclient` emits `StarletteDeprecationWarning: Using httpx with
starlette.testclient is deprecated; install httpx2 instead.` Non-blocking; no test
failures.

## Fixes applied

None. No broken import, path, or doc pointer was found in the assigned files, so this
change is **report-only**. `docs/SMOKE_W10.md` is the only file added.

## Notes

- The clean clone was left untouched except for the throwaway `.venv`, local test
  artifacts (`hermagotchi.db`), and the two `docs/evidence/*.log` files written by
  `scripts/hermes_check.sh`.
- No commit, tag, or push was performed; this report is left uncommitted.
