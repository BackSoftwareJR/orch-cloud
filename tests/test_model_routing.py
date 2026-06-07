"""Tests for per-preset and per-job Cursor model routing."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.models import AgentPreset, TaskRequest
from core.orchestrator import HyperOrchestrator
from core.presets.registry import (
    MODEL_REGISTRY,
    get_model_for_preset,
    resolve_model,
    validate_model,
)
from server.app import create_app
from server.config import get_agent_model_default
from server.orchestrator import build_command


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(create_app())


def test_model_registry_lists_allowed_slugs() -> None:
    assert "composer-2.5" in MODEL_REGISTRY
    assert "claude-4.6-sonnet-medium-thinking" in MODEL_REGISTRY
    assert MODEL_REGISTRY["composer-2.5"].tier == "composer"
    assert MODEL_REGISTRY["claude-4-sonnet"].tier == "api"


def test_preset_default_models() -> None:
    assert get_model_for_preset("general") == "composer-2.5"
    assert get_model_for_preset("ux") == "composer-2.5"
    assert get_model_for_preset("backend") == "claude-4.6-sonnet-medium-thinking"
    assert get_model_for_preset("bugfix") == "claude-4-sonnet"


def test_validate_model_accepts_known_slug() -> None:
    assert validate_model("composer-2.5") == "composer-2.5"


def test_validate_model_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Invalid model"):
        validate_model("not-a-real-model")


def test_resolve_model_uses_preset_default() -> None:
    assert resolve_model("backend", None) == "claude-4.6-sonnet-medium-thinking"


def test_resolve_model_honors_override() -> None:
    assert resolve_model("backend", "composer-2.5") == "composer-2.5"


def test_build_command_includes_resolved_model() -> None:
    cmd = build_command(
        "https://github.com/org/repo.git",
        "Add endpoint",
        "medium",
        "backend",
    )
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "claude-4.6-sonnet-medium-thinking"


def test_build_command_job_model_override() -> None:
    cmd = build_command(
        "https://github.com/org/repo.git",
        "Fix bug",
        "fast",
        "bugfix",
        model="composer-2.5",
    )
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "composer-2.5"


def test_agent_model_default_from_env() -> None:
    with patch.dict(os.environ, {"AGENT_MODEL_DEFAULT": "claude-4-sonnet"}, clear=False):
        assert get_agent_model_default() == "claude-4-sonnet"


def test_hyper_orchestrator_resolves_request_model() -> None:
    request = TaskRequest(
        repo_url="https://github.com/org/repo.git",
        task="Fix login",
        preset=AgentPreset.BACKEND,
        model="composer-2.5",
    )
    orchestrator = HyperOrchestrator(request, docker=object())  # type: ignore[arg-type]
    assert orchestrator.agent_model == "composer-2.5"


def test_hyper_orchestrator_falls_back_to_preset_model() -> None:
    request = TaskRequest(
        repo_url="https://github.com/org/repo.git",
        task="Fix login",
        preset=AgentPreset.BUGFIX,
    )
    orchestrator = HyperOrchestrator(request, docker=object())  # type: ignore[arg-type]
    assert orchestrator.agent_model == "claude-4-sonnet"


def test_list_models_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/models")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    slugs = {item["slug"] for item in body}
    assert "composer-2.5" in slugs
    assert "claude-4.6-sonnet-medium-thinking" in slugs
    first = body[0]
    assert {"slug", "label", "tier", "description"} <= set(first.keys())
