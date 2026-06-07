#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
VPS_IP="${VPS_IP:-2.24.15.210}"

echo "=== HyperOrchestrator connectivity diagnostics ==="
echo "Project root: $ROOT_DIR"
echo

if [[ -f "$ENV_FILE" ]]; then
  echo "==> .env contents (relevant keys):"
  grep -E '^(NEXT_PUBLIC_API_URL|INTERNAL_API_URL|CORS_ORIGINS)=' "$ENV_FILE" || echo "  (no API/CORS vars set)"
else
  echo "WARNING: $ENV_FILE not found"
fi
echo

echo "==> API service status:"
systemctl is-active orchestrator-api 2>/dev/null || echo "  orchestrator-api not found/inactive"
echo

echo "==> Dashboard service status:"
systemctl is-active orchestrator-dashboard 2>/dev/null || echo "  orchestrator-dashboard not found/inactive"
echo

echo "==> Direct API (localhost:8000):"
if curl -sf --max-time 5 http://127.0.0.1:8000/health; then
  echo
  echo "  OK — API responds on localhost:8000"
else
  echo "  FAIL — API not reachable on localhost:8000"
fi
echo

echo "==> Proxied API via dashboard (localhost:3000/api-backend):"
if curl -sf --max-time 5 http://127.0.0.1:3000/api-backend/health; then
  echo
  echo "  OK — Next.js proxy works"
else
  echo "  FAIL — proxy not working (rebuild dashboard after pulling latest code)"
fi
echo

echo "==> External API (browser would hit :8000 directly):"
if curl -sf --max-time 5 "http://${VPS_IP}:8000/health"; then
  echo
  echo "  OK — port 8000 open externally"
else
  echo "  FAIL — port 8000 blocked externally (expected on Hostinger; use /api-backend proxy)"
fi
echo

echo "==> External dashboard:"
if curl -sf --max-time 5 -o /dev/null -w "HTTP %{http_code}\n" "http://${VPS_IP}:3000/"; then
  echo "  OK — dashboard reachable"
else
  echo "  FAIL — dashboard not reachable on port 3000"
fi
echo

echo "==> Docker agent image:"
if docker image inspect hyper-agent-base >/dev/null 2>&1; then
  if docker run --rm hyper-agent-base cursor-agent --version >/dev/null 2>&1; then
    echo "  OK — hyper-agent-base with cursor-agent"
    docker run --rm hyper-agent-base cursor-agent --version 2>/dev/null | head -1 | sed 's/^/  /'
  else
    echo "  FAIL — hyper-agent-base exists but cursor-agent is missing"
    echo "  Fix: cd /opt/orch-cloud && docker build -t hyper-agent-base ."
  fi
else
  echo "  FAIL — hyper-agent-base image not built"
  echo "  Fix: cd /opt/orch-cloud && docker build -t hyper-agent-base ."
fi
echo

echo "==> Agent env file:"
AGENT_ENV="/opt/agent-orchestrator/config/agent.env"
if [[ -f "$AGENT_ENV" ]]; then
  if grep -q '^CURSOR_API_KEY=' "$AGENT_ENV"; then
    echo "  OK — CURSOR_API_KEY set in agent.env"
    if docker run --rm --env-file "$AGENT_ENV" hyper-agent-base \
      cursor-agent-entrypoint.sh -p --trust --sandbox disabled --force "Reply with OK" 2>&1 | head -5 | sed 's/^/  /'; then
      echo "  OK — cursor-agent responds inside container"
    else
      echo "  FAIL — cursor-agent failed inside container (check API key validity)"
    fi
  else
    echo "  FAIL — agent.env exists but CURSOR_API_KEY is missing"
  fi
else
  echo "  FAIL — $AGENT_ENV not found"
  echo "  Fix: sudo mkdir -p /opt/agent-orchestrator/config"
  echo "       echo 'CURSOR_API_KEY=your_key' | sudo tee $AGENT_ENV"
  echo "       sudo chmod 600 $AGENT_ENV"
fi
echo

echo "==> GitHub auth check:"
if [[ -n "${GITHUB_TOKEN:-}" || -n "${GH_TOKEN:-}" ]]; then
  echo "  GITHUB_TOKEN/GH_TOKEN is set"
elif [[ -f "${GITHUB_SSH_KEY_PATH:-$HOME/.ssh/orchestrator_deploy_key}" ]]; then
  echo "  Deploy key found at ${GITHUB_SSH_KEY_PATH:-$HOME/.ssh/orchestrator_deploy_key}"
elif [[ -f "$HOME/.ssh/id_ed25519" || -f "$HOME/.ssh/id_rsa" ]]; then
  echo "  Default SSH key found — ensure it has access to private repos"
else
  echo "  WARNING: no GITHUB_TOKEN or SSH deploy key — private repo clones will fail"
  echo "  Run: deploy/setup-github-deploy-key.sh"
fi
echo

echo "=== Done ==="
