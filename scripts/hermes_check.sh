#!/usr/bin/env bash
# Run Hermes plugin admission checks and keep bounded evidence logs.
#
# The script never dumps the environment or secret values. Command output is
# redirected to docs/evidence/*.log; only a short status line is printed.
set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVIDENCE_DIR="docs/evidence"
DOCTOR_LOG="$EVIDENCE_DIR/hermes_plugins_doctor.log"
VALIDATE_LOG="$EVIDENCE_DIR/hermes_plugins_validate.log"

cd "$ROOT" || {
  printf 'FAIL: cannot enter plugin root\n' >&2
  exit 1
}

mkdir -p "$EVIDENCE_DIR"
: >"$DOCTOR_LOG"
: >"$VALIDATE_LOG"

if ! command -v hermes >/dev/null 2>&1; then
  printf 'FAIL: hermes executable not found on PATH\n' | tee "$DOCTOR_LOG" >&2
  printf 'FAIL: hermes executable not found on PATH\n' >"$VALIDATE_LOG"
  exit 127
fi

status=0

{
  printf 'command: hermes plugins doctor .\n'
  printf 'cwd: plugin root\n'
  printf '%s\n' '---'
} >"$DOCTOR_LOG"

if hermes plugins doctor . >>"$DOCTOR_LOG" 2>&1; then
  printf 'PASS: hermes plugins doctor (log: %s)\n' "$DOCTOR_LOG"
else
  printf 'FAIL: hermes plugins doctor (log: %s)\n' "$DOCTOR_LOG" >&2
  status=1
fi

{
  printf 'command: hermes plugins validate . --install-deps\n'
  printf 'cwd: plugin root\n'
  printf '%s\n' '---'
} >"$VALIDATE_LOG"

if hermes plugins validate . --install-deps >>"$VALIDATE_LOG" 2>&1; then
  printf 'PASS: hermes plugins validate (log: %s)\n' "$VALIDATE_LOG"
else
  printf 'FAIL: hermes plugins validate (log: %s)\n' "$VALIDATE_LOG" >&2
  status=1
fi

exit "$status"
