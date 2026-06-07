#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "==> Stopping services..."
sudo systemctl stop orchestrator-dashboard orchestrator-api || true

echo "==> Pulling latest changes..."
git pull --ff-only

echo "==> Installing dashboard dependencies..."
cd dashboard
npm install --legacy-peer-deps

echo "==> Building dashboard..."
npm run build
cd "$ROOT_DIR"

echo "==> Restarting services..."
sudo systemctl start orchestrator-api orchestrator-dashboard

echo "==> Deploy complete."
