# Hermagotchi — release handoff

**Prepared:** 2026-11-06  
**Integration branch:** `feat/hackathon` (never `main`)  
**Deadline:** 2026-11-11 5:00 PM ET  
**State of this snapshot:** changes are intentionally **uncommitted**; the
launcher collects `git diff HEAD`.

This handoff is for Kyle/the release owner. It records what is ready, what is
still OPEN, and which submission steps are manual.

## 1. Pin the tip SHA

The catalog draft uses the explicit placeholder `REPLACE_WITH_40_CHAR_SHA`.
After the launcher/owner commits the collected diff on `feat/hackathon`, pin the
exact commit:

```bash
git switch feat/hackathon
git rev-parse HEAD
```

Copy that 40-character SHA into `docs/catalog/hermagotchi.yaml`:

```yaml
sha: REPLACE_WITH_40_CHAR_SHA  # replace with the full 40-character SHA
```

Do not use a short SHA, branch name or tag in the catalog entry. Re-run the
checks below after changing it. Do not merge to `main`.

## 2. Exact checks

Run from the repository root with the dev environment installed:

```bash
pip install -r requirements-dev.txt

python3 -m pytest -q tests/test_demo_docs.py
python3 -m pytest -q
python3 -m pytest -q server/tests

bash -n scripts/demo_local.sh

hermes plugins doctor .
hermes plugins validate . --install-deps

python3 evals/measure_schemas.py
```

Optional local smoke path:

```bash
bash scripts/demo_local.sh
```

The demo script binds only to `127.0.0.1`, uses a development auth stub, seeds a
local account, and requires no real API keys or cloud deployment.

Capture the doctor/validate output as submission evidence. If `hermes` is not on
`PATH`, record the tested Hermes version and the exact error instead of claiming
a pass.

## 3. Known gaps and OPEN items

| Area | Status |
|---|---|
| Hosted deploy | **OPEN** — no target chosen, no operator assigned, nothing deployed. This is an open decision for Kyle. |
| Catalog PR | **Not opened.** The YAML is in-repo only at `docs/catalog/hermagotchi.yaml`; the SHA is still a placeholder. |
| Art | The art worker is running in parallel on `feat/hackathon`. Placeholder or partial packs may remain; do not relabel them as final generated art. |
| Auth | The local server uses an `X-Account-Id` development stub. Production device pairing is not deployed or demonstrated. |
| Real PvP evidence | No hosted two-owner ranked match has been captured. Practice is implemented; do not present practice as PvP. |
| Security doc | README links `docs/SECURITY.md`. Confirm the security slice has landed that file before publishing; if it has not, add it or remove the link. |
| CI | CI ownership belongs to the W6-N slice. Do not change CI from this handoff. |
| Data deletion / retention | Hosted policy is TBD with the future operator. Local data is the configured SQLite file. |
| Catalog acceptance | Not claimed. Maintainer review has not happened. |

Do **not** open a PR to `NousResearch/hermes-agent` from this task. The catalog
draft is intentionally in-repo only.

## 4. Submission checklist — manual steps for Kyle

- [ ] Confirm the deadline and the current official submission form URL from the
      latest organizer announcement. Do not reuse an unverified URL.
- [ ] Choose the hosted target or explicitly submit the plugin as local-first.
      Hosted deployment remains OPEN until Kyle decides.
- [ ] Commit/collect the diff on `feat/hackathon`; never merge to `main`.
- [ ] Run `git rev-parse HEAD` and replace `REPLACE_WITH_40_CHAR_SHA` with the
      full 40-character SHA in `docs/catalog/hermagotchi.yaml`.
- [ ] Run the exact checks in section 2 and save the logs.
- [ ] Open the catalog PR against `NousResearch/hermes-agent` with the final
      YAML (manual action; not done here).
- [ ] Capture a <90-second demo following `docs/DEMO.md`. Label practice vs
      ranked, label partial art, and state that hosted is OPEN/not deployed.
- [ ] Post the demo only after owner authorization, tagging `@NousResearch`.
- [ ] Submit the catalog PR link, video link and any required form fields through
      the official form.
- [ ] Verify no secrets, API keys, tokens, tailnet hosts or personal filesystem
      paths appear in the PR, video, logs or screenshots.
- [ ] Record the final PR URL and submission receipt in this handoff.

## 5. Evidence ledger

| Area | Evidence to attach before submission |
|---|---|
| Source | Repo URL, branch `feat/hackathon`, release tag (if any), full tip SHA |
| Hermes | Tested Hermes version, `plugins doctor` log, `plugins validate` log |
| Tests | `pytest` summary and the demo-doc checks |
| Multiplayer | Two opaque account IDs (redacted), challenge/match IDs, replay hash — only if a real hosted match exists |
| Economy | Ledger/wallet reconciliation output and purchase/equip receipt |
| Assets | Art provenance, manifest pack ID, contact-sheet status; note placeholders |
| Social | Chat opt-in state, block/report evidence, moderation notice |
| Operations | Deployed URL or "not deployed"; backup/restore notes; outage behavior |
| Delivery | Catalog PR URL, demo video URL, form receipt |
| Gaps | The OPEN items in section 3 and the next three prioritized issues |

An item counts only when it has code, a passing check and real integration
evidence. Note what was not tested.
