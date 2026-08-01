#!/usr/bin/env bash
# Expose the local app to the internet via ngrok.
#
# Prereqs:
#   1. ngrok installed (https://ngrok.com/download)
#   2. ngrok authtoken configured once: ngrok config add-authtoken <token>
#   3. The app running (see scripts/ports.env for the backend port)
#
# Usage:
#   make prod          # in another terminal
#   ./scripts/share.sh
#
# For `make dev` (Vite dev server), instead run:
#   ./scripts/share.sh "$FRONTEND_PORT"   # after sourcing scripts/ports.env

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
# shellcheck disable=SC1091
[ -f "$ROOT/scripts/ports.env" ] && . "$ROOT/scripts/ports.env"
set +a
BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"

PORT="${1:-$BACKEND_PORT}"

if ! command -v ngrok >/dev/null 2>&1; then
  echo "ngrok is not installed."
  echo "Install from https://ngrok.com/download then run:"
  echo "  ngrok config add-authtoken <your-token>"
  exit 1
fi

if ! curl -fsS "http://127.0.0.1:${PORT}/api/v1/system/health" >/dev/null 2>&1; then
  if [ "$PORT" = "$BACKEND_PORT" ]; then
    if ! curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
      echo "Nothing is listening on http://127.0.0.1:${BACKEND_PORT}"
      echo "Start the app first, e.g.:"
      echo "  make prod"
      exit 1
    fi
  elif ! curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    echo "Nothing is listening on http://127.0.0.1:${PORT}"
    echo "Start the dev stack first, e.g.:"
    echo "  make dev"
    exit 1
  fi
fi

echo "==> Sharing http://127.0.0.1:${PORT} via ngrok"
echo "    Send your friend the https://....ngrok-free.app URL from the ngrok output."
echo "    Press Ctrl-C to stop the tunnel."
echo
echo "    Security: this exposes your local data with no login. Stop ngrok when done."
echo

exec ngrok http "$PORT"
