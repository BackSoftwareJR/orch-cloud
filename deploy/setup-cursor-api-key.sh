#!/usr/bin/env bash
set -euo pipefail

AGENT_ENV="/opt/agent-orchestrator/config/agent.env"
PROJECT_ENV="/opt/orch-cloud/.env"

echo "=== HyperOrchestrator — Cursor API key setup ==="
echo
echo "Generate a key at: Cursor Dashboard → Settings → API Keys"
echo

if [[ -n "${CURSOR_API_KEY:-}" ]]; then
  echo "Using CURSOR_API_KEY from current shell environment."
  KEY="$CURSOR_API_KEY"
else
  read -r -s -p "Paste CURSOR_API_KEY: " KEY
  echo
fi

if [[ -z "$KEY" ]]; then
  echo "ERROR: empty key — aborting."
  exit 1
fi

sudo mkdir -p "$(dirname "$AGENT_ENV")"
echo "CURSOR_API_KEY=$KEY" | sudo tee "$AGENT_ENV" >/dev/null
sudo chmod 600 "$AGENT_ENV"
echo "Wrote $AGENT_ENV"

if [[ ! -f "$PROJECT_ENV" ]]; then
  echo
  echo "Optional: also create $PROJECT_ENV for API/dashboard settings:"
  echo "  sudo cp /opt/orch-cloud/deploy/orchestrator.env.example $PROJECT_ENV"
fi

echo
echo "Restarting orchestrator-api..."
sudo systemctl restart orchestrator-api
echo "Done. Run: ./deploy/diagnose.sh"
