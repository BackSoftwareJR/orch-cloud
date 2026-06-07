"""Tests for Cursor API key settings endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.agent_env import get_cursor_api_key
from server.app import create_app
from server.config import get_agent_env_path


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    agent_env = tmp_path / "agent.env"
    monkeypatch.setenv("AGENT_ENV_PATH", str(agent_env))
    monkeypatch.setenv("REQUIRE_API_TOKEN", "false")
    with TestClient(create_app()) as client:
        yield client


def test_get_settings_unconfigured(api_client: TestClient) -> None:
    response = api_client.get("/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["cursor_api_key"]["configured"] is False
    assert body["cursor_api_key"]["masked_preview"] is None


def test_update_cursor_api_key(api_client: TestClient) -> None:
    response = api_client.put(
        "/settings/cursor-api-key",
        json={"api_key": "key_test_cursor_api_key_1234"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["masked_preview"].endswith("1234")
    assert body["masked_preview"].startswith("*")
    assert get_cursor_api_key(get_agent_env_path()) == "key_test_cursor_api_key_1234"


def test_update_rejects_short_key(api_client: TestClient) -> None:
    response = api_client.put(
        "/settings/cursor-api-key",
        json={"api_key": "short"},
    )
    assert response.status_code == 422


def test_delete_cursor_api_key(api_client: TestClient) -> None:
    api_client.put(
        "/settings/cursor-api-key",
        json={"api_key": "key_test_cursor_api_key_5678"},
    )
    response = api_client.delete("/settings/cursor-api-key")
    assert response.status_code == 204
    assert get_cursor_api_key(get_agent_env_path()) is None


def test_health_includes_cursor_key_status(api_client: TestClient) -> None:
    api_client.put(
        "/settings/cursor-api-key",
        json={"api_key": "key_test_cursor_api_key_abcd"},
    )
    response = api_client.get("/health")
    assert response.status_code == 200
    cursor = response.json()["cursor_api_key"]
    assert cursor["configured"] is True
    assert cursor["masked_preview"].endswith("abcd")


def test_settings_requires_token_when_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent_env = tmp_path / "agent.env"
    monkeypatch.setenv("AGENT_ENV_PATH", str(agent_env))
    monkeypatch.setenv("REQUIRE_API_TOKEN", "true")
    monkeypatch.setenv("ORCHESTRATOR_API_TOKEN", "secret-token")
    with TestClient(create_app()) as client:
        denied = client.put(
            "/settings/cursor-api-key",
            json={"api_key": "key_test_cursor_api_key_9999"},
        )
        assert denied.status_code == 401

        allowed = client.put(
            "/settings/cursor-api-key",
            json={"api_key": "key_test_cursor_api_key_9999"},
            headers={"Authorization": "Bearer secret-token"},
        )
        assert allowed.status_code == 200
