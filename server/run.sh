#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "Dashboard:       http://${HOST}:${PORT}/"
echo "Upload endpoint: http://${HOST}:${PORT}/upload"
echo "Stats API:       http://${HOST}:${PORT}/api/stats/summary"
echo "Set ESP APP_UPLOAD_URL to http://<this-machine-ip>:${PORT}/upload"
echo "Use HTTP (not HTTPS) for local dev to skip SNTP on the device."

exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
