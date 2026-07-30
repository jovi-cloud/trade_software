#!/usr/bin/env bash
# Run the backend and frontend together. Ctrl-C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup() {
  trap - INT TERM EXIT
  # Kill the whole process group so uvicorn's reloader children die too.
  kill 0 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "==> Applying migrations"
(cd "$ROOT/backend" && uv run alembic upgrade head)

echo "==> Backend  http://127.0.0.1:8000  (docs at /docs)"
(cd "$ROOT/backend" && uv run uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000) &

echo "==> Frontend http://localhost:5173"
(cd "$ROOT/frontend" && npm run dev) &

wait
