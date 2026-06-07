"""Tests for server-side CLI command construction."""

from __future__ import annotations

import os
from unittest.mock import patch

from core.models import AgentPreset
from server.orchestrator import _preset_cli_value, build_command


def test_preset_cli_value_normalizes_enum_repr() -> None:
    assert _preset_cli_value("AgentPreset.GENERAL") == "general"
    assert _preset_cli_value(AgentPreset.UX) == "ux"
    assert _preset_cli_value("backend") == "backend"


def test_build_command_uses_normalized_preset() -> None:
    cmd = build_command(
        "https://github.com/org/repo.git",
        "Fix layout",
        "medium",
        "AgentPreset.GENERAL",
    )
    preset_idx = cmd.index("--preset")
    assert cmd[preset_idx + 1] == "general"


def test_build_command_passes_max_retries_from_env() -> None:
    with patch.dict(os.environ, {"MAX_DEBUG_RETRIES": "6"}, clear=False):
        cmd = build_command(
            "https://github.com/org/repo.git",
            "Fix bug",
            "medium",
            "bugfix",
        )
    retries_idx = cmd.index("--max-retries")
    assert cmd[retries_idx + 1] == "6"


def test_build_command_max_retries_override() -> None:
    cmd = build_command(
        "https://github.com/org/repo.git",
        "Fix bug",
        "medium",
        "bugfix",
        max_retries=8,
    )
    retries_idx = cmd.index("--max-retries")
    assert cmd[retries_idx + 1] == "8"
