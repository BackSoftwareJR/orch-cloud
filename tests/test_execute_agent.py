"""Tests for n8n execute-agent endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.models import Job


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    db_path = tmp_path / "test.db"
    agent_env = tmp_path / "agent.env"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AGENT_ENV_PATH", str(agent_env))
    monkeypatch.setenv("ORCHESTRATOR_API_TOKEN", "n8n-test-key")
    with TestClient(create_app()) as client:
        yield client


def _execute_payload(**overrides: object) -> dict:
    base = {
        "dedicated_prompt": "Fix the homepage hero section",
        "github_url": "https://github.com/BackSoftwareJR/villa_sole",
        "specialist_role": "frontend dev",
        "task_id": "232",
        "project_id": "crm-proj-99",
        "website_url": "https://villa-sole.example.com",
        "crm_log_url": "https://crm.example.com/logs/232",
        "crm_auth_token": "crm-secret-token",
    }
    base.update(overrides)
    return base


def test_execute_agent_requires_api_key(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/execute-agent", json=_execute_payload())
    assert response.status_code == 401


def test_execute_agent_accepts_x_api_key(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/execute-agent",
        json=_execute_payload(),
        headers={"X-API-Key": "n8n-test-key"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["run_id"]
    assert body["task_id"]
    assert body["queue_position"] >= 1
    assert body["project_id"] >= 1
    assert body["orchestrator_job_id"] == body["run_id"]


def test_execute_agent_maps_frontend_to_ux_preset(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/execute-agent",
        json=_execute_payload(specialist_role="frontend dev"),
        headers={"X-API-Key": "n8n-test-key"},
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    from server.database import SessionLocal

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.job_id == run_id).one()
        assert job.preset == "ux"
        assert job.level == "medium"
        assert job.metadata_["crm_task_id"] == "232"
        assert job.metadata_["crm_project_id"] == "crm-proj-99"
        assert job.metadata_["website_url"] == "https://villa-sole.example.com"
        assert job.metadata_["crm_auth_token"] == "crm-secret-token"
    finally:
        db.close()


def test_execute_agent_reuses_project_for_same_github_url(api_client: TestClient) -> None:
    headers = {"X-API-Key": "n8n-test-key"}
    first = api_client.post(
        "/api/v1/execute-agent",
        json=_execute_payload(task_id="1"),
        headers=headers,
    )
    second = api_client.post(
        "/api/v1/execute-agent",
        json=_execute_payload(
            github_url="https://github.com/BackSoftwareJR/villa_sole.git",
            task_id="2",
        ),
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["project_id"] == second.json()["project_id"]


def test_api_usage_stats_after_execute_agent(api_client: TestClient) -> None:
    api_client.post(
        "/api/v1/execute-agent",
        json=_execute_payload(),
        headers={"X-API-Key": "n8n-test-key"},
    )
    stats = api_client.get("/stats/api-usage")
    assert stats.status_code == 200
    body = stats.json()
    assert body["total"] >= 1
    assert body["today"] >= 1
    assert body["by_source"].get("n8n", 0) >= 1
    assert len(body["recent"]) >= 1
