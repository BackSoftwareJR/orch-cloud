"""Git operations: clone, staging checkout, push with conflict handling."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from core.exceptions import GitConflictError, GitError
from core.git_auth import git_auth_remediation, git_subprocess_env, resolve_git_repo_url
from core.retry import retry_with_backoff
from core.security import validate_repo_url

logger = logging.getLogger(__name__)

DEFAULT_GIT_TIMEOUT = 300


class GitHubManager:
    """Manages repository clone, staging branch workflow, and push."""

    STAGING_BRANCH = "staging"

    def __init__(
        self,
        repo_url: str,
        work_dir: Path,
        *,
        timeout_seconds: int = DEFAULT_GIT_TIMEOUT,
    ) -> None:
        self.display_repo_url = validate_repo_url(repo_url.strip())
        self.repo_url, _ = resolve_git_repo_url(self.display_repo_url)
        self.work_dir = work_dir.resolve()
        self.timeout_seconds = timeout_seconds

    def clone_or_update(self) -> Path:
        """Clone repository or pull latest changes if already present."""
        if (self.work_dir / ".git").is_dir():
            self._ensure_remote_url()
            logger.info("Repository exists at %s — updating", self.work_dir)
            retry_with_backoff(
                lambda: self._run(["git", "fetch", "--all", "--prune"], cwd=self.work_dir),
                operation_name="git fetch",
                retryable=(GitError,),
            )
            branch = self.current_branch()
            retry_with_backoff(
                lambda: self._run(["git", "pull", "--ff-only", "origin", branch], cwd=self.work_dir, check=False),
                operation_name="git pull",
                retryable=(GitError,),
            )
            return self.work_dir

        self.work_dir.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Cloning %s into %s", self.display_repo_url, self.work_dir)

        def _clone() -> None:
            self._run(["git", "clone", self.repo_url, str(self.work_dir)])
            self._ensure_remote_url()

        retry_with_backoff(_clone, operation_name="git clone", retryable=(GitError,))
        return self.work_dir

    def _ensure_remote_url(self) -> None:
        self._run(
            ["git", "remote", "set-url", "origin", self.repo_url],
            cwd=self.work_dir,
            check=False,
        )

    def checkout_staging(self, create_if_missing: bool = True) -> None:
        """Align VPS with origin/staging, or create and push staging when absent."""
        cwd = self.work_dir
        self._run(["git", "fetch", "origin"], cwd=cwd)

        staging_exists = (
            self._branch_exists_local(self.STAGING_BRANCH)
            or self._branch_exists_remote(self.STAGING_BRANCH)
        )

        if staging_exists:
            if not self._branch_exists_local(self.STAGING_BRANCH):
                self._run(
                    ["git", "checkout", "-b", self.STAGING_BRANCH, f"origin/{self.STAGING_BRANCH}"],
                    cwd=cwd,
                )
            else:
                self._run(["git", "checkout", self.STAGING_BRANCH], cwd=cwd)

            if self._branch_exists_remote(self.STAGING_BRANCH):
                self._run(["git", "fetch", "origin"], cwd=cwd)
                self._run(
                    ["git", "reset", "--hard", f"origin/{self.STAGING_BRANCH}"],
                    cwd=cwd,
                )
                logger.info("Aligned local staging with origin/%s", self.STAGING_BRANCH)
            return

        if not create_if_missing:
            raise GitError(
                f"Staging branch '{self.STAGING_BRANCH}' does not exist",
                remediation=f"Create branch '{self.STAGING_BRANCH}' on the remote or allow auto-creation.",
            )

        base = self._default_base_branch()
        logger.info("Creating staging branch from %s and pushing to origin", base)
        self._run(["git", "checkout", base], cwd=cwd)
        self._run(["git", "pull", "origin", base], cwd=cwd, check=False)
        self._run(["git", "checkout", "-b", self.STAGING_BRANCH], cwd=cwd)
        self._run(["git", "push", "-u", "origin", self.STAGING_BRANCH], cwd=cwd)
        logger.info("Created and pushed origin/%s", self.STAGING_BRANCH)

    def stage_all_and_commit(self, message: str) -> bool:
        """Stage all changes and commit. Returns False if nothing to commit."""
        cwd = self.work_dir
        status = self._run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True)
        if not status.stdout.strip():
            logger.info("No changes to commit")
            return False

        self._run(["git", "add", "-A"], cwd=cwd)
        self._run(["git", "commit", "-m", message], cwd=cwd)
        return True

    def push_staging(self) -> None:
        """Push staging branch to origin, handling non-fast-forward gracefully."""

        def _push() -> None:
            self._run(["git", "push", "-u", "origin", self.STAGING_BRANCH], cwd=self.work_dir)
            logger.info("Pushed to origin/%s", self.STAGING_BRANCH)

        try:
            retry_with_backoff(_push, operation_name="git push", retryable=(GitError,))
        except GitError as exc:
            if "non-fast-forward" in str(exc).lower() or "rejected" in str(exc).lower():
                logger.warning("Push rejected — attempting rebase onto origin/staging")
                self._resolve_push_conflict()
            else:
                raise

    def reset_hard(self) -> None:
        """Discard all uncommitted changes (used for PRO rollback)."""
        self._run(["git", "reset", "--hard", "HEAD"], cwd=self.work_dir)
        self._run(["git", "clean", "-fd"], cwd=self.work_dir, check=False)
        logger.info("Reset working tree to HEAD")

    def _resolve_push_conflict(self) -> None:
        """Attempt rebase onto remote staging; abort and report on conflict."""
        cwd = self.work_dir
        self._run(["git", "fetch", "origin", self.STAGING_BRANCH], cwd=cwd)

        result = self._run(
            ["git", "rebase", f"origin/{self.STAGING_BRANCH}"],
            cwd=cwd,
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            self._run(["git", "rebase", "--abort"], cwd=cwd, check=False)
            raise GitConflictError(
                "Could not rebase onto origin/staging due to conflicts. "
                "Manual resolution required in the work directory.",
                remediation="Resolve conflicts in the work directory, then push manually.",
            )

        retry_with_backoff(
            lambda: self._run(["git", "push", "origin", self.STAGING_BRANCH], cwd=cwd),
            operation_name="git push after rebase",
            retryable=(GitError,),
        )
        logger.info("Push succeeded after rebase")

    def has_uncommitted_changes(self) -> bool:
        result = self._run(
            ["git", "status", "--porcelain"],
            cwd=self.work_dir,
            capture_output=True,
        )
        return bool(result.stdout.strip())

    def current_branch(self) -> str:
        result = self._run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.work_dir,
            capture_output=True,
        )
        return result.stdout.strip()

    def _default_base_branch(self) -> str:
        for branch in ("main", "master", "develop"):
            if self._branch_exists_remote(branch) or self._branch_exists_local(branch):
                return branch
        return "main"

    def _branch_exists_local(self, branch: str) -> bool:
        result = self._run(
            ["git", "show-ref", "--verify", f"refs/heads/{branch}"],
            cwd=self.work_dir,
            check=False,
            capture_output=True,
        )
        return result.returncode == 0

    def _branch_exists_remote(self, branch: str) -> bool:
        result = self._run(
            ["git", "show-ref", "--verify", f"refs/remotes/origin/{branch}"],
            cwd=self.work_dir,
            check=False,
            capture_output=True,
        )
        return result.returncode == 0

    def _run(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        check: bool = True,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        cmd_str = self._redact_cmd_for_log(cmd)
        cwd_str = str(cwd) if cwd else "(none)"
        logger.info("Git command: %s | cwd=%s", cmd_str, cwd_str)

        if not capture_output and check:
            capture_output = True

        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                check=False,
                capture_output=capture_output,
                text=True,
                timeout=self.timeout_seconds,
                env=git_subprocess_env(),
            )
        except FileNotFoundError as exc:
            logger.error(
                "Git command failed (git not found): %s | cwd=%s",
                cmd_str,
                cwd_str,
            )
            raise GitError(
                "git executable not found — is Git installed?",
                remediation="Install Git and ensure it is on your PATH.",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            logger.error(
                "Git command timed out after %ss: %s | cwd=%s",
                self.timeout_seconds,
                cmd_str,
                cwd_str,
            )
            raise GitError(
                f"Git command timed out after {self.timeout_seconds}s: {cmd_str}",
                remediation="Check network connectivity or increase timeout.",
            ) from exc

        if result.returncode == 0:
            logger.info("Git command succeeded (exit=0): %s | cwd=%s", cmd_str, cwd_str)
        else:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            logger.error(
                "Git command failed (exit=%s): %s | cwd=%s | stderr=%s | stdout=%s",
                result.returncode,
                cmd_str,
                cwd_str,
                stderr or "(empty)",
                stdout or "(empty)",
            )

        if check and result.returncode != 0:
            stderr = result.stderr.strip() if capture_output else ""
            stdout = result.stdout.strip() if capture_output else ""
            detail = stderr or stdout or f"exit code {result.returncode}"
            remediation = "Inspect git output above and verify credentials/branch state."
            auth_markers = (
                "could not read Username",
                "Authentication failed",
                "Permission denied",
                "invalid credentials",
                "Repository not found",
            )
            if any(marker.lower() in detail.lower() for marker in auth_markers):
                remediation = git_auth_remediation()
            raise GitError(
                f"Git command failed: {cmd_str} — {detail}",
                remediation=remediation,
            )

        return result

    @staticmethod
    def _redact_cmd_for_log(cmd: list[str]) -> str:
        parts: list[str] = []
        for part in cmd:
            if "x-access-token:" in part:
                parts.append(re.sub(r"x-access-token:[^@]+@", "x-access-token:***@", part))
            else:
                parts.append(part)
        return " ".join(parts)

    @staticmethod
    def sanitize_repo_name(repo_url: str) -> str:
        """Derive a filesystem-safe directory name from a repo URL."""
        name = repo_url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        name = re.sub(r"[^\w.\-]", "_", name)
        return name or "repository"
