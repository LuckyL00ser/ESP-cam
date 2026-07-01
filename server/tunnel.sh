#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

TARGET="${TUNNEL_TARGET:-http://127.0.0.1:8000}"
MAX_WAIT="${TUNNEL_WAIT_SECONDS:-60}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not found. Install it first: brew install cloudflared"
  exit 1
fi

echo "Waiting for API at ${TARGET}/health (up to ${MAX_WAIT}s)..."
deadline=$((SECONDS + MAX_WAIT))
until curl -sf "${TARGET}/health" >/dev/null; do
  if (( SECONDS >= deadline )); then
    echo "API not reachable at ${TARGET}."
    echo "Start the full stack first: docker compose up -d"
    echo "Or locally: ./run.sh"
    exit 1
  fi
  sleep 1
done

echo "API is ready."
echo "Starting Cloudflare quick tunnel to ${TARGET}"
echo "Use the https://....trycloudflare.com URL printed below."
echo "Tip: use 127.0.0.1 (not localhost) on macOS to avoid IPv6 issues."
exec cloudflared tunnel --url "${TARGET}"
