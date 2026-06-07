"""Tests for preset-aware test runner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from core.models import AgentPreset, TaskLevel
from core.presets.registry import PresetDefinition, get_preset
from core.test_runner import (
    format_test_failure_for_agent,
    is_lint_warnings_only,
    resolve_check_commands,
    run_preset_check,
)


def test_ux_preset_resolves_lint_then_build(tmp_path: Path) -> None:
    package = tmp_path / "package.json"
    package.write_text(
        json.dumps({"scripts": {"lint": "eslint .", "build": "next build", "test": "jest"}}),
        encoding="utf-8",
    )
    commands = resolve_check_commands("run_lint", tmp_path, "npm run test")
    assert commands == ["npm run lint", "npm run build"]


def test_bugfix_preset_uses_focused_script(tmp_path: Path) -> None:
    package = tmp_path / "package.json"
    package.write_text(
        json.dumps({"scripts": {"test:unit": "jest --selectProjects unit", "test": "jest"}}),
        encoding="utf-8",
    )
    commands = resolve_check_commands("run_focused", tmp_path, "npm run test")
    assert commands == ["npm run test:unit"]


def test_is_lint_warnings_only_detects_warning_output() -> None:
    logs = "✖ 3 problems (0 errors, 3 warnings)"
    assert is_lint_warnings_only(logs) is True
    assert is_lint_warnings_only("Error: something broke") is False


def test_run_preset_check_skipped_for_empty_commands() -> None:
    docker = MagicMock()
    preset = PresetDefinition(
        id=AgentPreset.GENERAL,
        label="Skip",
        description="",
        default_level=TaskLevel.MEDIUM,
        system_prompt="test",
        output_expectations="",
        test_strategy="skip",
    )
    result = run_preset_check(docker, Path("/tmp"), preset, "npm run test")
    assert result.skipped is True
    assert result.success is True
    docker.run_command.assert_not_called()


def test_format_test_failure_includes_command_and_logs() -> None:
    from core.test_runner import TestCheckResult

    result = TestCheckResult(
        success=False,
        command="npm run test",
        logs="FAIL src/foo.test.ts\nExpected 1 got 2",
    )
    formatted = format_test_failure_for_agent(result)
    assert "npm run test" in formatted
    assert "Expected 1 got 2" in formatted
