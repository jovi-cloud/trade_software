#!/usr/bin/env bash
# Run the backend and frontend together. Ctrl-C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Ports: edit scripts/ports.env (defaults 8001 / 5174).
set -a
# shellcheck disable=SC1091
[ -f "$ROOT/scripts/ports.env" ] && . "$ROOT/scripts/ports.env"
set +a
BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"
export BACKEND_PORT FRONTEND_PORT

cleanup() {
  trap - INT TERM EXIT
  # Kill the whole process group so uvicorn's reloader children die too.
  kill 0 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "==> Applying migrations"
(cd "$ROOT/backend" && uv run alembic upgrade head)

echo "==> Backend  http://127.0.0.1:${BACKEND_PORT}  (docs at /docs)"
(cd "$ROOT/backend" && uv run uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port "$BACKEND_PORT") &

echo "==> Frontend http://localhost:${FRONTEND_PORT}"
(cd "$ROOT/frontend" && npm run dev) &

wait
