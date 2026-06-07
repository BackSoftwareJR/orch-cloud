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

echo "==> ORCHESTRATOR_API_TOKEN (from .env and running API process):"
if [[ -f "$ENV_FILE" ]]; then
  grep -E '^(ORCHESTRATOR_API_TOKEN|WEBHOOK_TOKEN)=' "$ENV_FILE" | sed 's/=.*/=***masked***/' || echo "  (no API token vars in .env)"
else
  echo "  (.env missing)"
fi
if systemctl is-active orchestrator-api >/dev/null 2>&1; then
  PROC_ENV=$(systemctl show orchestrator-api -p Environment --value 2>/dev/null || true)
  if [[ "$PROC_ENV" == *ORCHESTRATOR_API_TOKEN=* ]]; then
    echo "  orchestrator-api process has ORCHESTRATOR_API_TOKEN set (via systemd EnvironmentFile)"
  else
    echo "  WARNING: orchestrator-api may not load ORCHESTRATOR_API_TOKEN — check /etc/systemd/system/orchestrator-api.service for EnvironmentFile=/opt/orch-cloud/.env"
  fi
  TOKEN=$(grep -E '^ORCHESTRATOR_API_TOKEN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d '' || true)
  if [[ -n "$TOKEN" ]]; then
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/api/v1/execute-agent       -H "Content-Type: application/json" -H "X-API-Key: $TOKEN"       -d '{"dedicated_prompt":"diagnose ping","github_url":"https://github.com/BackSoftwareJR/villa_sole"}')
    echo "  Local execute-agent auth test: HTTP $HTTP (expect 200)"
  fi
else
  echo "  orchestrator-api not running — skip auth test"
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
PROJECT_ENV="/opt/orch-cloud/.env"
HAS_KEY=0
if [[ -f "$AGENT_ENV" ]] && grep -q '^CURSOR_API_KEY=' "$AGENT_ENV"; then
  echo "  OK — CURSOR_API_KEY in $AGENT_ENV"
  HAS_KEY=1
elif [[ -f "$PROJECT_ENV" ]] && grep -q '^CURSOR_API_KEY=' "$PROJECT_ENV"; then
  echo "  OK — CURSOR_API_KEY in $PROJECT_ENV"
  HAS_KEY=1
fi
if [[ "$HAS_KEY" -eq 0 ]]; then
  if [[ -f "$AGENT_ENV" ]]; then
    echo "  FAIL — $AGENT_ENV exists but CURSOR_API_KEY is missing"
  else
    echo "  FAIL — CURSOR_API_KEY not found in $AGENT_ENV or $PROJECT_ENV"
  fi
  echo "  Fix: ./deploy/setup-cursor-api-key.sh"
else
  ENV_FILE="$AGENT_ENV"
  if [[ ! -f "$ENV_FILE" ]] || ! grep -q '^CURSOR_API_KEY=' "$ENV_FILE"; then
    ENV_FILE="$PROJECT_ENV"
  fi
  if docker run --rm --env-file "$ENV_FILE" hyper-agent-base \
    cursor-agent-entrypoint.sh -p --trust --sandbox disabled --force "Reply with OK" 2>&1 | head -5 | sed 's/^/  /'; then
    echo "  OK — cursor-agent responds inside container"
  else
    echo "  FAIL — cursor-agent failed (check API key validity at cursor.com/settings)"
  fi
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
