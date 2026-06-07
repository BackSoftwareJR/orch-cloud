"""Tests for agent preset registry and prompt integration."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from core.models import AgentPreset, TaskLevel, TaskRequest
from core.presets.registry import PRESET_SCHEMA_VERSION, get_preset, list_presets, resolve_level
from server.models import Job, JobStatus, Project
from server.webhook_callback import build_callback_payload, _sign_payload


def test_list_presets_includes_all_roles() -> None:
    ids = {preset.id.value for preset in list_presets()}
    assert ids == {"general", "ux", "backend", "bugfix"}


def test_agent_preset_from_value() -> None:
    assert AgentPreset.from_value("UX") == AgentPreset.UX
    assert AgentPreset.from_value(None) == AgentPreset.GENERAL
    assert AgentPreset.from_value("AgentPreset.GENERAL") == AgentPreset.GENERAL
    assert AgentPreset.from_value("AgentPreset.UX") == AgentPreset.UX
    assert AgentPreset.to_value("AgentPreset.GENERAL") == "general"
    assert AgentPreset.to_value(AgentPreset.UX) == "ux"


def test_get_preset_accepts_enum_repr_string() -> None:
    preset = get_preset("AgentPreset.GENERAL")
    assert preset.id == AgentPreset.GENERAL
    assert preset.label == "General"


def test_get_preset_accepts_enum_instance() -> None:
    preset = get_preset(AgentPreset.BACKEND)
    assert preset.id == AgentPreset.BACKEND


def test_resolve_level_uses_preset_default() -> None:
    assert resolve_level("bugfix", None) == TaskLevel.FAST
    assert resolve_level("ux", None) == TaskLevel.MEDIUM


def test_resolve_level_honors_override() -> None:
    assert resolve_level("bugfix", "pro") == TaskLevel.PRO


def test_preset_prompts_are_substantial() -> None:
    ux = get_preset("ux")
    assert len(ux.system_prompt) > 400
    assert "WCAG" in ux.system_prompt or "accessibility" in ux.system_prompt.lower()
    assert ux.constraints_block.startswith("## Preset constraints")
    assert len(ux.quality_checklist) >= 4


def test_quality_block_includes_checklist() -> None:
    backend = get_preset("backend")
    block = backend.quality_block
    assert "Quality checklist" in block
    for item in backend.quality_checklist:
        assert item in block


def test_preset_schema_version() -> None:
    assert get_preset("general").version == PRESET_SCHEMA_VERSION


def test_preset_test_strategies() -> None:
    assert get_preset("ux").test_strategy == "run_lint"
    assert get_preset("ux").push_on_test_failure is True
    assert get_preset("backend").test_strategy == "run"
    assert get_preset("bugfix").test_strategy == "run_focused"
    assert get_preset("general").test_strategy == "run"


def test_preset_default_models() -> None:
    assert get_preset("general").model == "composer-2.5"
    assert get_preset("ux").model == "composer-2.5"
    assert get_preset("backend").model == "claude-4.6-sonnet-medium-thinking"
    assert get_preset("bugfix").model == "claude-4-sonnet"


def test_task_request_accepts_preset() -> None:
    req = TaskRequest(
        repo_url="https://github.com/org/repo.git",
        task="Fix login page layout",
        preset=AgentPreset.UX,
    )
    assert req.preset == AgentPreset.UX


def test_webhook_payload_shape() -> None:
    job = Job(
        job_id="abc-123",
        project_id=1,
        status=JobStatus.COMPLETED,
        level="medium",
        preset="ux",
        task="Redesign homepage",
    )
    project = Project(id=1, name="Demo", repo_url="https://github.com/org/repo.git")
    payload = build_callback_payload(job, project)
    assert payload["event"] == "job.completed"
    assert payload["preset"] == "ux"
    assert payload["project_name"] == "Demo"


def test_webhook_signature_deterministic() -> None:
    body = json.dumps({"event": "job.completed"}).encode("utf-8")
    assert _sign_payload(body, "secret") == _sign_payload(body, "secret")
    assert _sign_payload(body, "secret") != _sign_payload(body, "other")
