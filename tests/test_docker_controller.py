"""Tests for DockerController agent env parsing."""

from __future__ import annotations

from pathlib import Path

from core.docker_controller import DockerController


def test_parse_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / "agent.env"
    env_file.write_text(
        '# comment\nCURSOR_API_KEY=test-key\nOPENAI_API_KEY="quoted"\n',
        encoding="utf-8",
    )
    env = DockerController._parse_env_file(env_file)
    assert env["CURSOR_API_KEY"] == "test-key"
    assert env["OPENAI_API_KEY"] == "quoted"
