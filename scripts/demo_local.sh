#!/usr/bin/env bash
# Local-only Hermagotchi demo.
#
# What this does:
#   1. Creates/uses a temporary virtualenv and installs requirements-dev.txt.
#   2. Creates a throwaway SQLite database and seeds one demo account.
#   3. Starts the FastAPI app on 127.0.0.1 only.
#   4. Prints and executes the /v1/healthz and POST /v1/pets steps.
#
# It never binds a public interface, never deploys to a cloud service and never
# reads or asks for a real API key. The account header is the local development
# auth stub, not production authentication.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${HERMAGOTCHI_DEMO_PORT:-8765}"
VENV_DIR="${HERMAGOTCHI_DEMO_VENV:-${TMPDIR:-/tmp}/hermagotchi-demo-venv}"
STATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/hermagotchi-demo.XXXXXX")"
export HERMAGOTCHI_DB="$STATE_DIR/hermagotchi-demo.db"

DEMO_ACCOUNT="00000000-0000-4000-8000-0000000000a1"
BASE_URL="http://127.0.0.1:${PORT}"
SERVER_PID=""

cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$STATE_DIR"
}
trap cleanup EXIT INT TERM

echo "== Hermagotchi local demo =="
echo "Repository: $(basename "$ROOT_DIR")"
echo "Bind: 127.0.0.1:${PORT} (loopback only)"
echo "Database: temporary SQLite file (removed on exit)"
echo "Network: local process only; no cloud deploy; no real API keys"
echo

echo "== Installing dev dependencies =="
python3 -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt
echo "Dependencies installed from requirements-dev.txt"
echo

echo "== Seeding local demo account =="
python - "$HERMAGOTCHI_DB" "$DEMO_ACCOUNT" <<'PY'
import sys

from server.app.db import connect, init_db, seed_account

db_path, account_id = sys.argv[1], sys.argv[2]
init_db(db_path)
conn = connect(db_path)
try:
    seed_account(conn, account_id, "demo_pilot")
finally:
    conn.close()
print(f"Seeded local development account: {account_id}")
PY
echo

echo "== Starting local server =="
if python -c 'import server.app.main as m; raise SystemExit(0 if hasattr(m, "app") else 1)' >/dev/null 2>&1; then
  python -m uvicorn server.app.main:app --host 127.0.0.1 --port "$PORT" &
else
  echo "server.app.main has no module-level app; using create_app factory"
  python -m uvicorn --factory server.app.main:create_app --host 127.0.0.1 --port "$PORT" &
fi
SERVER_PID=$!

echo "Waiting for readiness on ${BASE_URL}/v1/healthz ..."
ready=0
for _ in $(seq 1 100); do
  if curl -fsS "${BASE_URL}/v1/healthz" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.2
done
if [ "$ready" -ne 1 ]; then
  echo "Server did not become ready; see output above." >&2
  exit 1
fi

echo
echo "== Step 1: health check =="
echo "curl -fsS ${BASE_URL}/v1/healthz"
curl -fsS "${BASE_URL}/v1/healthz"
echo
echo

echo "== Step 2: adopt one local pet =="
echo "curl -fsS -X POST ${BASE_URL}/v1/pets \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'X-Account-Id: ${DEMO_ACCOUNT}' \\"
echo "  -d '{\"species\":\"patchfox\",\"name\":\"DemoFox\"}'"
curl -fsS -X POST "${BASE_URL}/v1/pets" \
  -H "Content-Type: application/json" \
  -H "X-Account-Id: ${DEMO_ACCOUNT}" \
  -d '{"species":"patchfox","name":"DemoFox"}'
echo
echo

cat <<EOF
== Reproduce by hand ==
export HERMAGOTCHI_DB=/tmp/hermagotchi-demo.db
python3 -m uvicorn --factory server.app.main:create_app --host 127.0.0.1 --port ${PORT}
# In another terminal:
curl -fsS ${BASE_URL}/v1/healthz
curl -fsS -X POST ${BASE_URL}/v1/pets \\
  -H 'Content-Type: application/json' \\
  -H 'X-Account-Id: ${DEMO_ACCOUNT}' \\
  -d '{"species":"patchfox","name":"DemoFox"}'

The X-Account-Id value is a local development stub, not a production login.
The server is loopback-only. Press Ctrl-C to stop.
EOF

wait "$SERVER_PID"
