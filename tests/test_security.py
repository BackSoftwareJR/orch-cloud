"""Unit tests for security helpers."""

from __future__ import annotations

import pytest

from core.exceptions import SecurityError
from core.security import redact_secrets, sanitize_task_prompt, validate_repo_url


def test_validate_repo_url_https() -> None:
    url = validate_repo_url("https://github.com/org/repo.git")
    assert url.startswith("https://")


def test_validate_repo_url_ssh() -> None:
    url = validate_repo_url("git@github.com:org/repo.git")
    assert url.startswith("git@")


def test_rejects_invalid_repo_url() -> None:
    with pytest.raises(SecurityError):
        validate_repo_url("not-a-url")


def test_rejects_shell_injection_in_url() -> None:
    with pytest.raises(SecurityError):
        validate_repo_url("https://github.com/org/repo.git; rm -rf /")


def test_sanitize_task_prompt() -> None:
    task = sanitize_task_prompt("  Fix the login bug  ")
    assert task == "Fix the login bug"


def test_redact_secrets() -> None:
    text = "api_key=sk-1234567890abcdef1234567890 and token=abc123secret"
    redacted = redact_secrets(text)
    assert "sk-1234567890abcdef1234567890" not in redacted
    assert "REDACTED" in redacted
