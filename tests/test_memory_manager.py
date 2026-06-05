"""Unit tests for MemoryManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.memory_manager import MemoryManager


@pytest.fixture
def memory(tmp_path: Path) -> MemoryManager:
    return MemoryManager(db_path=tmp_path / "test.db", stale_days=365)


def test_record_and_retrieve_pattern(memory: MemoryManager) -> None:
    project_key = "/tmp/test-project"
    memory.record_success_after_failures(
        project_key,
        "Fix login bug",
        error_pattern="SQLSTATE connection refused",
        solution_pattern="Updated DB_HOST in .env",
        failure_count=2,
    )
    patterns = memory.get_patterns(project_key, task="Fix login bug")
    assert len(patterns) == 1
    assert "SQLSTATE" in patterns[0].error_pattern
    assert patterns[0].relevance_score > 0


def test_pattern_deduplication(memory: MemoryManager) -> None:
    project_key = "/tmp/dedup"
    for _ in range(3):
        memory.record_success_after_failures(
            project_key,
            "Same task",
            error_pattern="Error X",
            solution_pattern="Fix Y",
            failure_count=1,
        )
    patterns = memory.get_patterns(project_key)
    assert len(patterns) == 1


def test_global_pattern_on_high_failures(memory: MemoryManager) -> None:
    project_key = "/tmp/global"
    memory.record_success_after_failures(
        project_key,
        "Hard task",
        error_pattern="OOM killed",
        solution_pattern="Increased memory limit",
        failure_count=5,
    )
    global_patterns = memory.get_patterns("__global__")
    assert any("OOM" in p.error_pattern for p in global_patterns)


def test_cursorrules_injection(memory: MemoryManager, tmp_path: Path) -> None:
    project_key = str(tmp_path)
    memory.record_success_after_failures(
        project_key,
        "Add feature",
        error_pattern="TypeError",
        solution_pattern="Added null check",
        failure_count=1,
    )
    patterns = memory.get_patterns(project_key)
    path = memory.inject_into_cursorrules(tmp_path, patterns, task="Add feature")
    content = path.read_text(encoding="utf-8")
    assert "hyper-orchestrator-learned-patterns" in content
    assert "TypeError" in content
    assert "Project-Specific Patterns" in content
