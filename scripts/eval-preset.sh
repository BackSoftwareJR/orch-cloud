#!/usr/bin/env bash
# Evaluate presets via dry-run (no Docker agent execution).
set -euo pipefail

REPO="${1:-https://github.com/BackSoftwareJR/orch-cloud}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT/.venv/bin/hyper-orchestrator"

if [[ ! -x "$CLI" ]]; then
  CLI="hyper-orchestrator"
fi

PRESETS=(general ux backend bugfix)

echo "=== Preset dry-run eval ==="
echo "Repo: $REPO"
echo

for preset in "${PRESETS[@]}"; do
  echo "--- preset: $preset ---"
  "$CLI" \
    --repo "$REPO" \
    --task "Dry-run validation for preset $preset" \
    --preset "$preset" \
    --dry-run \
    --json-log || exit 1
  echo
done

echo "All preset dry-runs passed."
