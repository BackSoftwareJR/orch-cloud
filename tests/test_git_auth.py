"""Tests for GitHub authentication URL resolution."""

from __future__ import annotations

import os
from unittest.mock import patch

from core.git_auth import (
    git_auth_remediation,
    https_github_to_ssh,
    inject_github_token,
    resolve_git_repo_url,
)


def test_inject_github_token() -> None:
    url = inject_github_token("https://github.com/org/repo.git", "ghp_secret")
    assert url == "https://x-access-token:ghp_secret@github.com/org/repo.git"


def test_https_github_to_ssh() -> None:
    url = https_github_to_ssh("https://github.com/BackSoftwareJR/cristinamalvini")
    assert url == "git@github.com:BackSoftwareJR/cristinamalvini.git"


def test_resolve_git_repo_url_with_token() -> None:
    with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test", "GH_TOKEN": ""}, clear=False):
        git_url, display = resolve_git_repo_url("https://github.com/org/repo.git")
    assert display == "https://github.com/org/repo.git"
    assert "x-access-token:ghp_test@" in git_url


def test_resolve_git_repo_url_ssh_passthrough() -> None:
    ssh = "git@github.com:org/repo.git"
    git_url, display = resolve_git_repo_url(ssh)
    assert git_url == ssh
    assert display == ssh


def test_git_auth_remediation_mentions_token_and_deploy_key() -> None:
    text = git_auth_remediation()
    assert "GITHUB_TOKEN" in text
    assert "setup-github-deploy-key" in text
