#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "==> Stopping services..."
sudo systemctl stop orchestrator-dashboard orchestrator-api || true

echo "==> Pulling latest changes..."
git pull --ff-only

if [[ -f "$ROOT_DIR/.env" ]]; then
  echo "==> Loading environment from .env..."
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
else
  echo "WARNING: $ROOT_DIR/.env not found — NEXT_PUBLIC_API_URL may be unset at build time."
fi

if [[ -z "${NEXT_PUBLIC_API_URL:-}" ]]; then
  echo "WARNING: NEXT_PUBLIC_API_URL is not set; dashboard will fall back to http://localhost:8000"
else
  echo "==> NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL"
fi

echo "==> Installing dashboard dependencies..."
cd dashboard
npm install --legacy-peer-deps

echo "==> Building dashboard (embedding NEXT_PUBLIC_API_URL)..."
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:8000}"
npm run build
cd "$ROOT_DIR"

echo "==> Restarting services..."
sudo systemctl start orchestrator-api orchestrator-dashboard

echo "==> Deploy complete."
