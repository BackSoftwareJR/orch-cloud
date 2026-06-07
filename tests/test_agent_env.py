"""Tests for agent environment resolution."""

from __future__ import annotations

from pathlib import Path

from core.agent_env import get_cursor_api_key, resolve_agent_env


def test_resolve_agent_env_prefers_process_env(tmp_path: Path, monkeypatch) -> None:
    agent_env = tmp_path / "agent.env"
    agent_env.write_text("CURSOR_API_KEY=file-key\n", encoding="utf-8")
    monkeypatch.setenv("CURSOR_API_KEY", "process-key")
    merged = resolve_agent_env(agent_env)
    assert merged["CURSOR_API_KEY"] == "process-key"


def test_get_cursor_api_key_from_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    agent_env = tmp_path / "agent.env"
    agent_env.write_text("CURSOR_API_KEY=abc123\n", encoding="utf-8")
    assert get_cursor_api_key(agent_env) == "abc123"
