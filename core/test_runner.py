"""Preset-aware test/check resolution and execution."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from core.docker_controller import DockerController
from core.presets.registry import PresetDefinition, TestStrategy
from core.security import redact_secrets

logger = logging.getLogger(__name__)

LINT_WARNING_MARKERS = ("warning", "warn ")
LINT_ERROR_MARKERS = ("error", "failed", "exception", "fatal")


@dataclass(frozen=True)
class TestCheckResult:
    """Outcome of a preset-aware validation command."""

    success: bool
    command: str
    logs: str
    skipped: bool = False
    warnings_only: bool = False
    strategy: TestStrategy = "run"


def _read_package_scripts(project_root: Path) -> dict[str, str]:
    package_json = project_root / "package.json"
    if not package_json.is_file():
        return {}
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


def _npm_script_exists(project_root: Path, script: str) -> bool:
    return script in _read_package_scripts(project_root)


def resolve_check_commands(
    strategy: TestStrategy,
    project_root: Path,
    fallback_command: str,
) -> list[str]:
    """Return ordered shell commands to try for a preset test strategy."""
    if strategy == "skip":
        return []

    if strategy == "run_lint":
        commands: list[str] = []
        if _npm_script_exists(project_root, "lint"):
            commands.append("npm run lint")
        if _npm_script_exists(project_root, "build"):
            commands.append("npm run build")
        return commands or ([fallback_command] if fallback_command else [])

    if strategy == "run_build":
        if _npm_script_exists(project_root, "build"):
            return ["npm run build"]
        return [fallback_command] if fallback_command else []

    if strategy == "run_focused":
        scripts = _read_package_scripts(project_root)
        for name in ("test:unit", "test:related", "test:fast", "test"):
            if name in scripts:
                return [f"npm run {name}"]
        return [fallback_command] if fallback_command else []

    # run — full suite (backend, general, bugfix default)
    return [fallback_command] if fallback_command else []


def is_lint_warnings_only(logs: str) -> bool:
    """Heuristic: lint exited non-zero but output looks like warnings only."""
    lower = logs.lower()
    if any(marker in lower for marker in LINT_ERROR_MARKERS):
        if " 0 errors" in lower or "0 error" in lower:
            return True
        if "error" in lower and "warning" in lower and "errors" not in lower.split("error")[0][-20:]:
            pass
        else:
            return False
    return any(marker in lower for marker in LINT_WARNING_MARKERS)


def format_test_failure_for_agent(result: TestCheckResult, *, max_chars: int = 12000) -> str:
    """Full test output for fix agents (not just error signature)."""
    header = f"Command: {result.command}\nExit: {'0' if result.success else 'non-zero'}\n\n"
    body = redact_secrets(result.logs.strip())
    if len(body) > max_chars:
        body = body[-max_chars:]
        body = f"(…truncated to last {max_chars} chars)\n{body}"
    return header + body


def run_preset_check(
    docker: DockerController,
    project_root: Path,
    preset: PresetDefinition,
    fallback_command: str,
) -> TestCheckResult:
    """Run the appropriate validation command(s) for a preset."""
    commands = resolve_check_commands(preset.test_strategy, project_root, fallback_command)
    if not commands:
        logger.info("Preset %s — test strategy skip (no commands)", preset.id.value)
        return TestCheckResult(
            success=True,
            command="(skipped)",
            logs="",
            skipped=True,
            strategy=preset.test_strategy,
        )

    last_result: TestCheckResult | None = None
    for command in commands:
        logger.info("Running preset check [%s]: %s", preset.test_strategy, command)
        container_result = docker.run_command(project_root, command)
        check = TestCheckResult(
            success=container_result.success,
            command=command,
            logs=container_result.logs,
            strategy=preset.test_strategy,
        )
        if check.success:
            return check

        warnings_only = (
            preset.test_strategy in ("run_lint", "run_build")
            and is_lint_warnings_only(check.logs)
        )
        check = TestCheckResult(
            success=False,
            command=command,
            logs=check.logs,
            warnings_only=warnings_only,
            strategy=preset.test_strategy,
        )
        last_result = check
        if preset.test_strategy == "run_lint" and command == "npm run lint":
            continue

    assert last_result is not None
    return last_result
