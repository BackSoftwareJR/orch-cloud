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

echo "=== Done ==="
