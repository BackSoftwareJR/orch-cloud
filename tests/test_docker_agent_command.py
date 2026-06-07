"""Tests for Docker agent CLI command construction."""

from __future__ import annotations

from core.docker_controller import AGENT_BINARY, DockerController


def test_build_agent_command_uses_headless_cursor_cli_flags() -> None:
    cmd = DockerController._build_agent_command(
        "Fix the news page layout",
        model="composer-2.5",
        yolo=True,
    )
    assert cmd[0] == AGENT_BINARY
    assert "-p" in cmd
    assert "--trust" in cmd
    assert "--workspace" in cmd
    assert "--model" in cmd
    assert "--force" in cmd
    assert "--prompt" not in cmd
    assert cmd[-1] == "Fix the news page layout"


def test_format_agent_command_for_log_truncates_long_prompts() -> None:
    cmd = DockerController._build_agent_command("x" * 200, model="composer-2.5", yolo=False)
    rendered = DockerController._format_agent_command_for_log(cmd)
    assert "…" in rendered
    assert "xxx" in rendered
