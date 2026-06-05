"""Unit tests for GitHubManager staging checkout behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from core.exceptions import GitError
from core.github_manager import GitHubManager


@pytest.fixture
def git_manager(tmp_path: Path) -> GitHubManager:
    work_dir = tmp_path / "repo"
    work_dir.mkdir()
    return GitHubManager("https://github.com/example/acme.git", work_dir)


def _mock_branch_checks(
    manager: GitHubManager,
    *,
    local: set[str] | None = None,
    remote: set[str] | None = None,
) -> None:
    local = local or set()
    remote = remote or set()

    def exists_local(branch: str) -> bool:
        return branch in local

    def exists_remote(branch: str) -> bool:
        return branch in remote

    manager._branch_exists_local = MagicMock(side_effect=exists_local)  # type: ignore[method-assign]
    manager._branch_exists_remote = MagicMock(side_effect=exists_remote)  # type: ignore[method-assign]


def test_checkout_staging_resets_when_remote_exists(git_manager: GitHubManager) -> None:
    _mock_branch_checks(git_manager, local={"staging"}, remote={"staging"})
    run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    git_manager._run = run  # type: ignore[method-assign]

    git_manager.checkout_staging()

    run.assert_has_calls(
        [
            call(["git", "fetch", "origin"], cwd=git_manager.work_dir),
            call(["git", "checkout", "staging"], cwd=git_manager.work_dir),
            call(["git", "fetch", "origin"], cwd=git_manager.work_dir),
            call(["git", "reset", "--hard", "origin/staging"], cwd=git_manager.work_dir),
        ]
    )


def test_checkout_staging_tracks_remote_when_local_missing(git_manager: GitHubManager) -> None:
    _mock_branch_checks(git_manager, local=set(), remote={"staging"})
    run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    git_manager._run = run  # type: ignore[method-assign]

    git_manager.checkout_staging()

    run.assert_any_call(
        ["git", "checkout", "-b", "staging", "origin/staging"],
        cwd=git_manager.work_dir,
    )
    run.assert_any_call(
        ["git", "reset", "--hard", "origin/staging"],
        cwd=git_manager.work_dir,
    )


def test_checkout_staging_creates_and_pushes_when_missing(git_manager: GitHubManager) -> None:
    _mock_branch_checks(git_manager, local={"main"}, remote={"main"})
    run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    git_manager._run = run  # type: ignore[method-assign]
    git_manager._default_base_branch = MagicMock(return_value="main")  # type: ignore[method-assign]

    git_manager.checkout_staging()

    run.assert_any_call(["git", "checkout", "main"], cwd=git_manager.work_dir)
    run.assert_any_call(["git", "checkout", "-b", "staging"], cwd=git_manager.work_dir)
    run.assert_any_call(
        ["git", "push", "-u", "origin", "staging"],
        cwd=git_manager.work_dir,
    )


def test_checkout_staging_raises_when_missing_and_create_disabled(
    git_manager: GitHubManager,
) -> None:
    _mock_branch_checks(git_manager, local=set(), remote=set())
    git_manager._run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))  # type: ignore[method-assign]

    with pytest.raises(GitError, match="does not exist"):
        git_manager.checkout_staging(create_if_missing=False)
