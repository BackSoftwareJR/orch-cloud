#!/usr/bin/env bash
set -euo pipefail

KEY_PATH="${1:-$HOME/.ssh/orchestrator_deploy_key}"
SSH_DIR="$(dirname "$KEY_PATH")"

echo "==> Generating GitHub deploy key at $KEY_PATH"
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

if [[ -f "$KEY_PATH" ]]; then
  echo "Key already exists — reusing $KEY_PATH"
else
  ssh-keygen -t ed25519 -C "hyper-orchestrator-vps" -f "$KEY_PATH" -N ""
fi

chmod 600 "$KEY_PATH"

echo
echo "==> Add this public key to GitHub (repo → Settings → Deploy keys → Add):"
echo
cat "${KEY_PATH}.pub"
echo
echo "==> Then add to /opt/orch-cloud/.env (optional, if not using default path):"
echo "GITHUB_SSH_KEY_PATH=$KEY_PATH"
echo
echo "==> Test access (replace org/repo):"
echo "GIT_SSH_COMMAND=\"ssh -i $KEY_PATH -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes\" \\"
echo "  git ls-remote git@github.com:BackSoftwareJR/cristinamalvini.git"
