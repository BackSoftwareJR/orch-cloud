"""Resolve Cursor agent credentials from env files and process environment."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from server.config import PROJECT_ROOT

DEFAULT_AGENT_ENV = Path("/opt/agent-orchestrator/config/agent.env")
AGENT_ENV_KEYS = ("CURSOR_API_KEY", "OPENAI_API_KEY")
CURSOR_API_KEY_MIN_LEN = 8
CURSOR_API_KEY_MAX_LEN = 512


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


def mask_cursor_api_key(key: str) -> str:
    """Return a masked preview showing only the last four characters."""
    cleaned = key.strip()
    if len(cleaned) <= 4:
        return "****"
    return f"{'*' * (len(cleaned) - 4)}{cleaned[-4:]}"


def validate_cursor_api_key(key: str) -> str:
    """Validate and normalize a Cursor API key before persistence."""
    cleaned = key.strip()
    if not cleaned:
        raise ValueError("API key cannot be empty")
    if len(cleaned) < CURSOR_API_KEY_MIN_LEN or len(cleaned) > CURSOR_API_KEY_MAX_LEN:
        raise ValueError(
            f"API key length must be between {CURSOR_API_KEY_MIN_LEN} and "
            f"{CURSOR_API_KEY_MAX_LEN} characters"
        )
    return cleaned


def _set_env_file_value(path: Path, key: str, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    found = False
    if path.is_file():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                existing_key, _, _ = line.partition("=")
                if existing_key.strip() == key:
                    lines.append(f"{key}={value}")
                    found = True
                    continue
            lines.append(raw_line)
    if not found:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _remove_env_file_value(path: Path, key: str) -> None:
    if not path.is_file():
        return
    kept: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            existing_key, _, _ = line.partition("=")
            if existing_key.strip() == key:
                continue
        kept.append(raw_line)
    if kept:
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    else:
        path.unlink(missing_ok=True)


def set_cursor_api_key(key: str, agent_env_path: Path | None = None) -> Path:
    """Persist CURSOR_API_KEY to agent.env and update the current process env."""
    path = agent_env_path or DEFAULT_AGENT_ENV
    normalized = validate_cursor_api_key(key)
    _set_env_file_value(path, "CURSOR_API_KEY", normalized)
    os.environ["CURSOR_API_KEY"] = normalized
    return path


def clear_cursor_api_key(agent_env_path: Path | None = None) -> Path:
    """Remove CURSOR_API_KEY from agent.env and the current process env."""
    path = agent_env_path or DEFAULT_AGENT_ENV
    _remove_env_file_value(path, "CURSOR_API_KEY")
    os.environ.pop("CURSOR_API_KEY", None)
    return path


def cursor_api_key_status(agent_env_path: Path | None = None) -> dict[str, object]:
    """Return masked Cursor API key status for settings/health endpoints."""
    path = agent_env_path or DEFAULT_AGENT_ENV
    key = get_cursor_api_key(path)
    updated_at: datetime | None = None
    if path.is_file():
        updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return {
        "configured": bool(key),
        "masked_preview": mask_cursor_api_key(key) if key else None,
        "updated_at": updated_at,
        "source_path": str(path),
    }
