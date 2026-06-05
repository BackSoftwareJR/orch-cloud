"""Tests for ProjectNotInitializedError handling."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from core.docker_controller import DockerController, _selinux_z_enabled
from core.exceptions import ProjectNotInitializedError
from core.memory_manager import MemoryManager
from core.models import LearnedPattern, TaskLevel, TaskRequest
from core.orchestrator import HyperOrchestrator


def test_docker_run_agent_raises_when_project_missing(tmp_path: Path) -> None:
    controller = DockerController()
    missing = tmp_path / "missing-repo"

    with patch.object(controller, "ensure_base_image"):
        with pytest.raises(ProjectNotInitializedError, match="does not exist"):
            controller.run_agent(missing, "do something")


def test_docker_run_command_raises_when_project_missing(tmp_path: Path) -> None:
    controller = DockerController()
    missing = tmp_path / "missing-repo"

    with patch.object(controller, "ensure_base_image"):
        with pytest.raises(ProjectNotInitializedError, match="does not exist"):
            controller.run_command(missing, "echo hi")


def test_memory_inject_raises_when_project_missing(tmp_path: Path) -> None:
    memory = MemoryManager(db_path=tmp_path / "learning.db")
    missing = tmp_path / "missing-repo"
    pattern = LearnedPattern(
        project_key="test",
        error_pattern="err",
        solution_pattern="fix",
    )

    with pytest.raises(ProjectNotInitializedError, match="project directory missing"):
        memory.inject_into_cursorrules(missing, [pattern])


def test_orchestrator_analyze_raises_when_repo_missing(tmp_path: Path) -> None:
    missing = tmp_path / "not-cloned"
    request = TaskRequest(
        repo_url="https://github.com/example/acme.git",
        task="fix bug",
        level=TaskLevel.FAST,
        work_dir=str(missing),
        dry_run=False,
    )
    orchestrator = HyperOrchestrator(request)

    with patch.object(orchestrator, "_prepare_repository"):
        orchestrator.project_root = missing
        with pytest.raises(ProjectNotInitializedError, match="does not exist"):
            orchestrator._analyze_project()


def test_selinux_z_respects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_SELINUX_Z", "true")
    assert _selinux_z_enabled() is True

    monkeypatch.setenv("DOCKER_SELINUX_Z", "false")
    assert _selinux_z_enabled() is False


def test_bind_mount_mode_adds_z_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_SELINUX_Z", "true")
    assert DockerController._bind_mount_mode("rw") == "rw,z"
    assert DockerController._bind_mount_mode("ro") == "ro,z"
