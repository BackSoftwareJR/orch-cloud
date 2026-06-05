"""Unit tests for PRO task plan validation."""

from __future__ import annotations

import pytest

from core.exceptions import TaskPlanError
from core.task_planner import validate_and_order_plan


def test_validate_simple_plan() -> None:
    plan = validate_and_order_plan(
        [
            {"id": 1, "title": "Step 1", "description": "Do first thing"},
            {"id": 2, "title": "Step 2", "description": "Do second thing", "depends_on": [1]},
        ],
        summary="Two-step plan",
    )
    assert len(plan.tasks) == 2
    assert plan.tasks[0].id == 1
    assert plan.tasks[1].depends_on == [1]


def test_rejects_duplicate_ids() -> None:
    with pytest.raises(TaskPlanError, match="Duplicate"):
        validate_and_order_plan(
            [
                {"id": 1, "title": "A", "description": "a"},
                {"id": 1, "title": "B", "description": "b"},
            ]
        )


def test_rejects_circular_dependencies() -> None:
    with pytest.raises(TaskPlanError, match="Circular"):
        validate_and_order_plan(
            [
                {"id": 1, "title": "A", "description": "a", "depends_on": [2]},
                {"id": 2, "title": "B", "description": "b", "depends_on": [1]},
            ]
        )


def test_rejects_unknown_dependency() -> None:
    with pytest.raises(TaskPlanError, match="unknown task"):
        validate_and_order_plan(
            [{"id": 1, "title": "A", "description": "a", "depends_on": [99]}]
        )


def test_topological_ordering() -> None:
    plan = validate_and_order_plan(
        [
            {"id": 3, "title": "Third", "description": "c", "depends_on": [2]},
            {"id": 1, "title": "First", "description": "a"},
            {"id": 2, "title": "Second", "description": "b", "depends_on": [1]},
        ]
    )
    ids = [t.id for t in plan.tasks]
    assert ids.index(1) < ids.index(2) < ids.index(3)
