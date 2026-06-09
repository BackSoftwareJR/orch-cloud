"""Tests for CRM/n8n outbound callback helpers."""

from __future__ import annotations

from server.models import Job, JobStatus
from server.webhook_callback import (
    build_crm_completed_payload,
    build_crm_log_payload,
    build_crm_status_payload,
    build_job_metadata_from_execute_agent,
    parse_crm_callbacks,
)
from server.schemas import ExecuteAgentRequest


def _sample_metadata() -> dict[str, str]:
    return {
        "crm_task_id": "232",
        "crm_project_id": "41",
        "callback_status_url": "https://crm.example.com/api/webhooks/n8n/status",
        "callback_completed_url": "https://crm.example.com/api/webhooks/n8n/completed",
        "callback_task_log_url": "https://crm.example.com/api/webhooks/n8n/task-log",
        "callback_url": "https://crm.example.com/api/webhooks/n8n/task-events",
        "callback_close_task_url": "https://crm.example.com/api/webhooks/n8n/close-task",
        "callback_auth_header": "authbs",
        "crm_auth_token": "secret-token",
    }


def test_parse_crm_callbacks_workspace_agent() -> None:
    metadata = {**_sample_metadata(), "crm_task_id": "workspace_agent_7"}
    config = parse_crm_callbacks(metadata)
    assert config is not None
    assert config.task_id == "workspace_agent_7"
    assert config.status_url.endswith("/status")
    assert config.auth_header == "authbs"
    assert config.auth_value == "secret-token"


def test_build_job_metadata_from_execute_agent() -> None:
    payload = ExecuteAgentRequest(
        dedicated_prompt="Do the thing",
        exact_prompt=True,
        github_url="https://github.com/org/repo",
        task_id="workspace_agent_3",
        project_id="99",
        callback_status_url="https://crm.example.com/status",
        callback_auth_header="authbs",
        crm_auth_token="tok",
    )
    metadata = build_job_metadata_from_execute_agent(payload)
    assert metadata["crm_task_id"] == "workspace_agent_3"
    assert metadata["crm_project_id"] == "99"
    assert metadata["callback_status_url"] == "https://crm.example.com/status"
    assert metadata["callback_auth_header"] == "authbs"
    assert metadata["crm_auth_token"] == "tok"
    assert metadata["exact_prompt"] == "true"


def test_build_crm_status_payload() -> None:
    job = Job(
        job_id="run-uuid-1",
        status=JobStatus.RUNNING,
        metadata_=_sample_metadata(),
        task="test",
        level="medium",
        preset="general",
        project_id=1,
    )
    payload = build_crm_status_payload(job, message="Agent started", progress=10)
    assert payload["task_id"] == "232"
    assert payload["project_id"] == "41"
    assert payload["status"] == "running"
    assert payload["run_id"] == "run-uuid-1"
    assert payload["progress"] == 10


def test_build_crm_completed_payload_success() -> None:
    job = Job(
        job_id="run-uuid-2",
        status=JobStatus.COMPLETED,
        metadata_=_sample_metadata(),
        task="test",
        level="medium",
        preset="general",
        project_id=1,
    )
    payload = build_crm_completed_payload(job)
    assert payload["status"] == "completed"
    assert payload["result"]["job_id"] == "run-uuid-2"


def test_build_crm_completed_payload_failed() -> None:
    job = Job(
        job_id="run-uuid-3",
        status=JobStatus.FAILED,
        metadata_=_sample_metadata(),
        task="test",
        level="medium",
        preset="general",
        project_id=1,
        error_message="exit 1",
    )
    payload = build_crm_completed_payload(job)
    assert payload["status"] == "failed"
    assert payload["error"] == "exit 1"


def test_build_crm_log_payload() -> None:
    payload = build_crm_log_payload("run-1", _sample_metadata(), "  hello world\n")
    assert payload["task_id"] == "232"
    assert payload["message"] == "  hello world"
    assert payload["log_message"] == "  hello world"
