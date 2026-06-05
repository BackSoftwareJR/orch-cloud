"""PRO-level task plan validation, ordering, and rollback helpers."""

from __future__ import annotations

import logging
from collections import deque

from core.exceptions import TaskPlanError
from core.models import AtomicTask, TaskPlan

logger = logging.getLogger(__name__)


def validate_and_order_plan(raw_tasks: list[dict[str, object]], summary: str = "") -> TaskPlan:
    """Validate task decomposition schema and order by dependencies."""
    if not raw_tasks:
        raise TaskPlanError(
            "Task plan contains no tasks.",
            remediation="Ensure the decomposition model returns at least one atomic task.",
        )

    tasks: list[AtomicTask] = []
    seen_ids: set[int] = set()

    for raw in raw_tasks:
        if not isinstance(raw, dict):
            raise TaskPlanError(f"Invalid task entry (expected object): {raw!r}")
        try:
            task = AtomicTask.model_validate(raw)
        except Exception as exc:
            raise TaskPlanError(f"Invalid atomic task schema: {exc}") from exc

        if task.id in seen_ids:
            raise TaskPlanError(f"Duplicate task id: {task.id}")
        seen_ids.add(task.id)

        if not task.title.strip():
            raise TaskPlanError(f"Task {task.id} has empty title")
        if not task.description.strip():
            raise TaskPlanError(f"Task {task.id} has empty description")

        tasks.append(task)

    ordered = _topological_sort(tasks)
    return TaskPlan(tasks=ordered, summary=summary)


def _topological_sort(tasks: list[AtomicTask]) -> list[AtomicTask]:
    """Order tasks respecting depends_on; raise on cycles or missing deps."""
    by_id = {t.id: t for t in tasks}
    in_degree = {t.id: 0 for t in tasks}
    adjacency: dict[int, list[int]] = {t.id: [] for t in tasks}

    for task in tasks:
        for dep in task.depends_on:
            if dep not in by_id:
                raise TaskPlanError(
                    f"Task {task.id} depends on unknown task {dep}",
                    remediation="Ensure all depends_on IDs reference tasks in the plan.",
                )
            adjacency[dep].append(task.id)
            in_degree[task.id] += 1

    queue: deque[int] = deque(tid for tid, deg in in_degree.items() if deg == 0)
    ordered: list[AtomicTask] = []

    while queue:
        tid = queue.popleft()
        ordered.append(by_id[tid])
        for neighbor in adjacency[tid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered) != len(tasks):
        raise TaskPlanError(
            "Circular dependency detected in task plan.",
            remediation="Remove circular depends_on references from the decomposition.",
        )

    return ordered


def rollback_completed_steps(
    git_manager: object,
    completed_task_ids: list[int],
) -> None:
    """Best-effort rollback: reset uncommitted changes after PRO step failure."""
    has_changes = getattr(git_manager, "has_uncommitted_changes", lambda: False)
    reset = getattr(git_manager, "reset_hard", None)
    if callable(has_changes) and has_changes() and callable(reset):
        logger.warning(
            "Rolling back uncommitted changes after failure at steps %s",
            completed_task_ids,
        )
        reset()
