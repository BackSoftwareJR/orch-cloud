"""Pre-flight health checks before orchestration runs."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from core.docker_controller import DockerController
from core.exceptions import HealthCheckError
from core.security import check_ssh_key_permissions, validate_repo_url

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Outcome of pre-flight checks."""

    passed: bool
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def raise_if_failed(self) -> None:
        if not self.passed:
            failed = [c for c in self.checks if c.startswith("FAIL:")]
            msg = "; ".join(failed) or "Health checks failed"
            raise HealthCheckError(
                msg,
                remediation=(
                    "Fix the failed checks above. Common fixes: start Docker, "
                    "build hyper-agent-base image, create agent.env, fix SSH key permissions."
                ),
            )


def run_preflight_checks(
    *,
    repo_url: str,
    docker: DockerController,
    agent_env_path: Path | None = None,
    ssh_dir: Path | None = None,
    require_openai: bool = False,
) -> HealthCheckResult:
    """Run all pre-flight health checks."""
    import os

    checks: list[str] = []
    warnings: list[str] = []
    passed = True

    def ok(name: str) -> None:
        checks.append(f"OK: {name}")

    def fail(name: str, detail: str) -> None:
        nonlocal passed
        passed = False
        checks.append(f"FAIL: {name} — {detail}")

    def warn(name: str, detail: str) -> None:
        warnings.append(f"WARN: {name} — {detail}")

    # Git
    if shutil.which("git"):
        ok("git installed")
    else:
        fail("git installed", "git executable not found in PATH")

    # Repo URL
    try:
        validate_repo_url(repo_url)
        ok("repo URL valid")
    except Exception as exc:
        fail("repo URL valid", str(exc))

    # Docker
    if DockerController.is_docker_available():
        ok("Docker daemon reachable")
    else:
        fail("Docker daemon reachable", "Docker is not running or not accessible")

    # Base image
    try:
        docker.ensure_base_image()
        ok(f"Docker image '{docker.base_image}' available")
    except Exception as exc:
        fail(f"Docker image '{docker.base_image}'", str(exc))

    # Agent env
    env_path = agent_env_path or docker.agent_env_path
    if env_path.is_file():
        ok(f"agent.env exists at {env_path}")
    else:
        warn(
            "agent.env",
            f"Not found at {env_path} — Cursor API key may be missing in containers",
        )

    # SSH
    ssh = ssh_dir or docker.ssh_dir
    if ssh.is_dir():
        ok(f"SSH directory exists at {ssh}")
        for warning in check_ssh_key_permissions(ssh):
            warn("SSH key permissions", warning)
    else:
        warn("SSH directory", f"Not found at {ssh} — git push from containers may fail")

    # OpenAI for PRO
    if require_openai:
        if os.environ.get("OPENAI_API_KEY"):
            ok("OPENAI_API_KEY set")
        else:
            fail("OPENAI_API_KEY set", "Required for PRO-level task decomposition")

    logger.info("Pre-flight checks: passed=%s warnings=%d", passed, len(warnings))
    return HealthCheckResult(passed=passed, checks=checks, warnings=warnings)
