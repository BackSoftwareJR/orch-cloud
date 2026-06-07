"""Resolve authenticated Git remote URLs for non-interactive VPS clones."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from core.security import validate_repo_url

_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})


def inject_github_token(url: str, token: str) -> str:
    """Embed a GitHub PAT in an HTTPS remote URL."""
    parsed = urlparse(url)
    if parsed.username:
        return url
    netloc = f"x-access-token:{token}@{parsed.hostname}"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


def https_github_to_ssh(url: str) -> str:
    """Convert https://github.com/org/repo to git@github.com:org/repo.git."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in _GITHUB_HOSTS:
        return url

    path = parsed.path.strip("/")
    if not path:
        return url

    repo_path = path if path.endswith(".git") else f"{path}.git"
    return f"git@github.com:{repo_path}"


def _github_ssh_key_path() -> Path | None:
    explicit = os.environ.get("GITHUB_SSH_KEY_PATH", "").strip()
    if explicit:
        key = Path(explicit).expanduser()
        return key if key.is_file() else None

    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.is_dir():
        return None

    for name in ("orchestrator_deploy_key", "id_ed25519", "id_rsa"):
        key = ssh_dir / name
        if key.is_file():
            return key
    return None


def git_subprocess_env() -> dict[str, str]:
    """Environment for non-interactive git on headless servers."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "/bin/false"

    key_path = _github_ssh_key_path()
    if key_path is not None:
        env["GIT_SSH_COMMAND"] = (
            f"ssh -i {key_path} -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes"
        )
    return env


def resolve_git_repo_url(repo_url: str) -> tuple[str, str]:
    """
    Return (git_remote_url, display_url).

    display_url is safe for logs; git_remote_url may include token auth or SSH.
    """
    display_url = validate_repo_url(repo_url.strip())

    if display_url.startswith("git@"):
        return display_url, display_url

    parsed = urlparse(display_url)
    if parsed.scheme not in ("http", "https"):
        return display_url, display_url

    host = (parsed.hostname or "").lower()
    if host not in _GITHUB_HOSTS:
        return display_url, display_url

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return inject_github_token(display_url, token.strip()), display_url

    if _github_ssh_key_path() is not None:
        return https_github_to_ssh(display_url), display_url

    return display_url, display_url


def git_auth_remediation() -> str:
    """Human-readable fix when GitHub auth fails on a headless server."""
    return (
        "Configure GitHub access on the VPS: "
        "(1) set GITHUB_TOKEN in /opt/orch-cloud/.env, or "
        "(2) run deploy/setup-github-deploy-key.sh and add the public key to the repo, "
        "or (3) register the project with an SSH URL (git@github.com:org/repo.git)."
    )
