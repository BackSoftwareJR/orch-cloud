#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Generated or build-time files that often differ on the VPS after `npm run build`.
DEPLOY_RESET_PATHS=(
  dashboard/next-env.d.ts
)

reset_deploy_artifacts() {
  for p in "${DEPLOY_RESET_PATHS[@]}"; do
    if git ls-files --error-unmatch "$p" &>/dev/null; then
      git restore "$p" 2>/dev/null || git checkout -- "$p" 2>/dev/null || true
    elif [[ -e "$p" ]]; then
      rm -f "$p"
    fi
  done
}

prepare_git_for_pull() {
  reset_deploy_artifacts
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "==> Local changes detected; stashing before pull..."
    git stash push -u -m "deploy-autostash $(date +%Y%m%d%H%M%S)"
  fi
}

echo "==> Stopping services..."
sudo systemctl stop orchestrator-dashboard orchestrator-api || true

echo "==> Pulling latest changes..."
prepare_git_for_pull
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

echo "==> Reloading systemd units (pick up any unit file changes)..."
sudo systemctl daemon-reload

echo "==> Restarting services..."
sudo systemctl start orchestrator-api orchestrator-dashboard

echo "==> Deploy complete."
