"""Tests for model failover execution routing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import logging
import pytest

from core.docker_controller import ContainerRunResult
from core.execution_router import (
    FALLBACK_CHAIN,
    ExecutionRouter,
    log_model_switch,
    resolve_model_chain,
)
from core.supervisor import summarize_run


@dataclass
class _FakeDocker:
    calls: list[str]
    outcomes: list[ContainerRunResult]

    def run_agent(self, project_root: Path, prompt: str, *, model: str, yolo: bool) -> ContainerRunResult:
        self.calls.append(model)
        if self.outcomes:
            return self.outcomes.pop(0)
        return ContainerRunResult(exit_code=0, logs="task completed", container_id="x", success=True)


def test_fallback_chain_order() -> None:
    assert FALLBACK_CHAIN == ("claude-4.6-sonnet", "composer-2.5", "auto")


def test_resolve_model_chain_starts_at_member() -> None:
    assert resolve_model_chain("composer-2.5") == ["composer-2.5", "auto"]


def test_resolve_model_chain_prepends_unknown_model() -> None:
    chain = resolve_model_chain("claude-4.6-sonnet-medium-thinking")
    assert chain[0] == "claude-4.6-sonnet-medium-thinking"
    assert chain[1:] == list(FALLBACK_CHAIN)


def test_run_agent_failover_on_failure() -> None:
    docker = _FakeDocker(
        calls=[],
        outcomes=[
            ContainerRunResult(exit_code=1, logs="fatal error", container_id="a", success=False),
            ContainerRunResult(exit_code=0, logs="task completed", container_id="b", success=True),
        ],
    )
    router = ExecutionRouter(docker=docker)  # type: ignore[arg-type]

    outcome = router.run_agent(
        Path("/tmp/project"),
        "do work",
        model="claude-4.6-sonnet",
        yolo=True,
    )

    assert docker.calls == ["claude-4.6-sonnet", "composer-2.5"]
    assert outcome.result.success is True
    assert outcome.model_used == "composer-2.5"
    assert len(outcome.model_switches) == 1
    assert outcome.model_switches[0]["from_model"] == "claude-4.6-sonnet"
    assert outcome.model_switches[0]["to_model"] == "composer-2.5"


def test_run_agent_stops_after_chain_exhausted() -> None:
    docker = _FakeDocker(
        calls=[],
        outcomes=[
            ContainerRunResult(exit_code=1, logs="error", container_id="a", success=False),
            ContainerRunResult(exit_code=1, logs="error", container_id="b", success=False),
            ContainerRunResult(exit_code=1, logs="error", container_id="c", success=False),
        ],
    )
    router = ExecutionRouter(docker=docker)  # type: ignore[arg-type]

    outcome = router.run_agent(Path("/tmp/project"), "do work", model="claude-4.6-sonnet")

    assert docker.calls == list(FALLBACK_CHAIN)
    assert outcome.result.success is False
    assert outcome.model_used == "auto"
    assert len(outcome.model_switches) == 2


def test_log_model_switch_json(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="core.execution_router"):
        event = log_model_switch(
            from_model="composer-2.5",
            to_model="auto",
            reason="agent_failure",
            json_logs=True,
        )
    assert event["event"] == "model_switch"
    assert "model_switch" in caplog.text


def test_supervisor_summarize_run_success() -> None:
    result = ContainerRunResult(
        exit_code=0,
        logs="Modified src/app.py successfully",
        container_id="id",
        success=True,
    )
    checkpoint = summarize_run(result, result.logs, model="composer-2.5", attempt=1)
    assert checkpoint["status"] == "success"
    assert checkpoint["model"] == "composer-2.5"
    assert checkpoint["attempt"] == 1
    assert "src/app.py" in checkpoint["files_touched"]
