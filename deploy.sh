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
  echo "WARNING: $ROOT_DIR/.env not found."
fi

export INTERNAL_API_URL="${INTERNAL_API_URL:-http://127.0.0.1:8000}"
echo "==> INTERNAL_API_URL=$INTERNAL_API_URL (Next.js proxy target)"

echo "==> Installing dashboard dependencies..."
cd dashboard
npm install --legacy-peer-deps

echo "==> Building dashboard with API proxy (/api-backend → $INTERNAL_API_URL)..."
export INTERNAL_API_URL
npm run build
cd "$ROOT_DIR"

echo "==> Building Docker agent image (hyper-agent-base)..."
docker build -t hyper-agent-base .

echo "==> Restarting services..."
sudo systemctl start orchestrator-api orchestrator-dashboard

echo "==> Deploy complete."
