"""Context window management for agent prompts."""

from __future__ import annotations

import re

_SECTION_HEADER = re.compile(r"^## (.+)$", re.MULTILINE)

# Priority order for sections when truncating context
_SECTION_PRIORITY = {
    "laravel overview": 1,
    "next.js overview": 1,
    "unknown framework": 1,
    "dependencies": 2,
    "scripts": 2,
    "routes": 3,
    "router structure": 3,
    "migrations": 4,
    "models": 4,
    "controllers": 4,
    "middleware": 5,
    "api routes": 5,
    "testing": 6,
    "environment": 7,
    "service providers": 8,
    "typescript paths": 9,
}


def prioritize_context(
    summary: str,
    *,
    max_chars: int = 6000,
    task: str = "",
    section_priorities: dict[str, int] | None = None,
) -> str:
    """Return the most relevant portions of .system_context.md for a prompt."""
    if len(summary) <= max_chars:
        return summary

    sections: list[tuple[str, str, int]] = []
    matches = list(_SECTION_HEADER.finditer(summary))
    if not matches:
        return summary[:max_chars]

    for idx, match in enumerate(matches):
        title = match.group(1)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(summary)
        body = summary[start:end].strip()
        priority = _section_priority(title, task, section_priorities)
        sections.append((title, body, priority))

    sections.sort(key=lambda s: s[2])

    parts: list[str] = []
    total = 0
    for title, body, _ in sections:
        chunk = f"## {title}\n\n{body}\n"
        if total + len(chunk) > max_chars:
            remaining = max_chars - total
            if remaining > 200:
                parts.append(chunk[:remaining] + "\n\n_[truncated]_")
            break
        parts.append(chunk)
        total += len(chunk)

    return "\n".join(parts)


def _section_priority(
    title: str,
    task: str,
    section_priorities: dict[str, int] | None = None,
) -> int:
    """Lower number = higher priority."""
    key = title.lower()
    if section_priorities:
        for pattern, priority in section_priorities.items():
            if pattern in key:
                return priority
    base = _SECTION_PRIORITY.get(key, 50)

    task_lower = task.lower()
    if "route" in task_lower and "route" in key:
        return 0
    if "test" in task_lower and "test" in key:
        return 0
    if "model" in task_lower and "model" in key:
        return 0
    if "migration" in task_lower and "migration" in key:
        return 0
    if "middleware" in task_lower and "middleware" in key:
        return 0

    return base
