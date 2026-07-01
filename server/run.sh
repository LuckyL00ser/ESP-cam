#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

uv sync

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "Dashboard:       http://${HOST}:${PORT}/"
echo "Upload endpoint: http://${HOST}:${PORT}/upload"
echo "Stats API:       http://${HOST}:${PORT}/api/stats/summary"
echo "Set ESP APP_UPLOAD_URL to http://<this-machine-ip>:${PORT}/upload"
echo "Use HTTP (not HTTPS) for local dev to skip SNTP on the device."

exec uv run uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
