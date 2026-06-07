#!/usr/bin/env bash
set -euo pipefail

if [[ -f /workspace/.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /workspace/.env
  set +a
fi

if [[ -z "${CURSOR_API_KEY:-}" ]]; then
  echo "[cursor-agent] ERROR: CURSOR_API_KEY is not set inside the container." >&2
  echo "[cursor-agent] Create /opt/agent-orchestrator/config/agent.env on the VPS with:" >&2
  echo "[cursor-agent]   CURSOR_API_KEY=your_key_from_cursor_dashboard" >&2
  exit 2
fi

if ! command -v cursor-agent >/dev/null 2>&1; then
  echo "[cursor-agent] ERROR: cursor-agent binary not found in PATH." >&2
  exit 127
fi

echo "[cursor-agent] auth=key-present model=${CURSOR_MODEL:-${CURSOR_AGENT_MODEL:-cli-arg}}" >&2
exec cursor-agent "$@"
