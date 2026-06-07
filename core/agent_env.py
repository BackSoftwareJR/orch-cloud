"""Resolve Cursor agent credentials from env files and process environment."""

from __future__ import annotations

import os
from pathlib import Path

from server.config import PROJECT_ROOT

DEFAULT_AGENT_ENV = Path("/opt/agent-orchestrator/config/agent.env")
AGENT_ENV_KEYS = ("CURSOR_API_KEY", "OPENAI_API_KEY")


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}

    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            env[key] = value
    return env


def resolve_agent_env(agent_env_path: Path | None = None) -> dict[str, str]:
    """Merge agent secrets from agent.env, project .env, and process environment."""
    path = agent_env_path or DEFAULT_AGENT_ENV
    merged: dict[str, str] = {}

    for env_path in (path, PROJECT_ROOT / ".env"):
        merged.update(parse_env_file(env_path))

    for key in AGENT_ENV_KEYS:
        if os.environ.get(key):
            merged[key] = os.environ[key]

    return merged


def get_cursor_api_key(agent_env_path: Path | None = None) -> str | None:
    return resolve_agent_env(agent_env_path).get("CURSOR_API_KEY") or None


def agent_env_sources_checked(agent_env_path: Path | None = None) -> list[Path]:
    path = agent_env_path or DEFAULT_AGENT_ENV
    sources = [path, PROJECT_ROOT / ".env"]
    return [source for source in sources if source.is_file()]
