"""Supervisor checkpoint scaffold — summarizes run state after each attempt."""

from __future__ import annotations

import re
from typing import Any

from core.docker_controller import ContainerRunResult
from core.models import OrchestrationResult

_FILE_LINE = re.compile(
    r"(?:editing|modified|writing|updated|created|changed)\s+[`']?"
    r"([^\s'`\"]+\.[A-Za-z0-9]+)",
    re.IGNORECASE,
)


def _extract_files_from_logs(logs: str, *, limit: int = 20) -> list[str]:
    seen: set[str] = set()
    files: list[str] = []
    for match in _FILE_LINE.finditer(logs):
        path = match.group(1).strip().rstrip(".,;:")
        if path not in seen:
            seen.add(path)
            files.append(path)
        if len(files) >= limit:
            break
    return files


def _suggest_next_steps(
    result: OrchestrationResult | ContainerRunResult,
    logs: str,
) -> list[str]:
    success = result.success
    if success:
        return ["Review changes and merge when ready"]

    lower = logs.lower()
    steps: list[str] = ["Inspect agent logs for the root error"]
    if "rate limit" in lower or "429" in lower:
        steps.append("Wait for rate limits to clear or switch execution mode")
    if "test" in lower or "pytest" in lower or "npm err" in lower:
        steps.append("Fix failing tests before re-running the task")
    if not steps:
        steps.append("Retry with a narrower task scope or different preset")
    return steps


def summarize_run(
    result: OrchestrationResult | ContainerRunResult,
    logs: str,
    *,
    model: str | None = None,
    attempt: int | None = None,
) -> dict[str, Any]:
    """Build a short checkpoint JSON after an agent or orchestration attempt."""
    checkpoint: dict[str, Any] = {
        "status": "success" if result.success else "failed",
        "files_touched": _extract_files_from_logs(logs),
        "next_steps": _suggest_next_steps(result, logs),
    }
    if model is not None:
        checkpoint["model"] = model
    if attempt is not None:
        checkpoint["attempt"] = attempt
    if isinstance(result, OrchestrationResult):
        checkpoint["message"] = result.message
        checkpoint["tasks_completed"] = result.tasks_completed
    elif hasattr(result, "exit_code"):
        checkpoint["exit_code"] = result.exit_code  # type: ignore[union-attr]
    return checkpoint
