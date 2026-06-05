"""Parse container logs to detect agent completion vs failure."""

from __future__ import annotations

import re

_SUCCESS_MARKERS = (
    "task completed",
    "successfully completed",
    "done.",
    "finished successfully",
    "changes applied",
)

_FAILURE_MARKERS = (
    "unhandled exception",
    "traceback (most recent call last)",
    "fatal error",
    "agent error",
    "permission denied",
    "command not found",
    "rate limit",
    "authentication failed",
)

_COMPLETION_PATTERN = re.compile(
    r"(?:completed|finished|done)\s*(?:successfully)?",
    re.IGNORECASE,
)


def is_agent_success(logs: str, exit_code: int) -> bool:
    """Determine whether an agent run succeeded based on exit code and log content."""
    if exit_code != 0:
        return False
    lower = logs.lower()
    if any(marker in lower for marker in _FAILURE_MARKERS):
        return False
    if any(marker in lower for marker in _SUCCESS_MARKERS):
        return True
    if _COMPLETION_PATTERN.search(logs):
        return True
    # Exit 0 with no failure markers is treated as success
    return True


def extract_progress_events(logs: str) -> list[str]:
    """Extract human-readable progress lines from agent logs."""
    progress: list[str] = []
    for line in logs.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if any(
            token in lower
            for token in ("step", "working", "editing", "running", "thinking", "applying")
        ):
            progress.append(stripped[:200])
    return progress[-10:]
