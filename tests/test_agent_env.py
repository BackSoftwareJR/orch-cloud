"""Tests for agent environment resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.agent_env import (
    clear_cursor_api_key,
    get_cursor_api_key,
    mask_cursor_api_key,
    resolve_agent_env,
    set_cursor_api_key,
    validate_cursor_api_key,
)


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


def test_mask_cursor_api_key() -> None:
    assert mask_cursor_api_key("key_abcdefghijklmnop") == "****************mnop"


def test_set_and_clear_cursor_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    agent_env = tmp_path / "agent.env"
    set_cursor_api_key("key_test_cursor_api_key_0001", agent_env)
    assert get_cursor_api_key(agent_env) == "key_test_cursor_api_key_0001"
    assert "OPENAI_API_KEY" not in agent_env.read_text(encoding="utf-8")
    clear_cursor_api_key(agent_env)
    assert get_cursor_api_key(agent_env) is None


def test_validate_cursor_api_key_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_cursor_api_key("   ")
