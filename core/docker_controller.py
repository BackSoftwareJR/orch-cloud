"""Docker container management for ephemeral agent execution."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import docker
from docker.errors import DockerException, ImageNotFound, NotFound
from docker.models.containers import Container

from core.exceptions import DockerOrchestratorError
from core.log_parser import extract_progress_events, is_agent_success
from core.retry import retry_with_backoff
from core.security import check_ssh_key_permissions, redact_secrets

logger = logging.getLogger(__name__)

DEFAULT_BASE_IMAGE = "hyper-agent-base"
DEFAULT_AGENT_ENV = Path("/opt/agent-orchestrator/config/agent.env")
AGENT_BINARY = "cursor-agent"


@dataclass
class ContainerRunResult:
    """Outcome of a containerized agent run."""

    exit_code: int
    logs: str
    container_id: str
    duration_seconds: float = 0.0
    success: bool = False


@dataclass
class DockerController:
    """Spins up ephemeral containers with repo, env, and SSH mounts."""

    base_image: str = DEFAULT_BASE_IMAGE
    agent_env_path: Path = field(default_factory=lambda: DEFAULT_AGENT_ENV)
    ssh_dir: Path = field(default_factory=lambda: Path.home() / ".ssh")
    network_mode: str = "bridge"

    def __post_init__(self) -> None:
        self._client: docker.DockerClient | None = None

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            try:
                self._client = docker.from_env()
                self._client.ping()
            except DockerException as exc:
                raise DockerOrchestratorError(
                    "Docker is unavailable. Ensure Docker daemon is running.",
                    remediation="Start Docker Desktop or the docker systemd service, then retry.",
                ) from exc
        return self._client

    def ensure_base_image(self) -> None:
        try:
            self.client.images.get(self.base_image)
            logger.debug("Base image %s is available", self.base_image)
        except ImageNotFound as exc:
            raise DockerOrchestratorError(
                f"Base image '{self.base_image}' not found.",
                remediation=f"Build it with: docker build -t {self.base_image} .",
            ) from exc

    def validate_mounts(self) -> list[str]:
        """Return warnings about mount configuration."""
        warnings: list[str] = []
        if not self.agent_env_path.is_file():
            warnings.append(
                f"Agent env not found at {self.agent_env_path} — mount /workspace/.env will be skipped"
            )
        if not self.ssh_dir.is_dir():
            warnings.append(f"SSH dir not found at {self.ssh_dir} — git push from containers may fail")
        else:
            warnings.extend(check_ssh_key_permissions(self.ssh_dir))
        return warnings

    def run_agent(
        self,
        project_root: Path,
        prompt: str,
        *,
        model: str = "composer-2.5",
        yolo: bool = False,
        working_dir: str = "/workspace",
        timeout_seconds: int = 3600,
        extra_env: dict[str, str] | None = None,
    ) -> ContainerRunResult:
        """Run cursor-agent in an ephemeral container."""
        self.ensure_base_image()
        project_root = project_root.resolve()

        if not project_root.is_dir():
            raise ValueError(
                f"Project root does not exist: {project_root}",
            )

        volumes = self._build_volumes(project_root)
        command = self._build_agent_command(prompt, model=model, yolo=yolo)

        env = {"CURSOR_AGENT_MODEL": model}
        if extra_env:
            env.update(extra_env)

        container_name = f"hyper-agent-{int(time.time())}"
        logger.info(
            "Starting container %s (model=%s, yolo=%s)",
            container_name,
            model,
            yolo,
        )

        start = time.monotonic()
        container: Container | None = None

        def _run_container() -> ContainerRunResult:
            nonlocal container
            container = self.client.containers.run(
                self.base_image,
                command=command,
                name=container_name,
                volumes=volumes,
                working_dir=working_dir,
                environment=env,
                detach=True,
                remove=False,
                network_mode=self.network_mode,
            )
            exit_code = self._wait_with_progress(container, timeout_seconds)
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            duration = time.monotonic() - start
            success = is_agent_success(logs, int(exit_code))
            logger.info(
                "Container %s finished exit=%d success=%s in %.1fs",
                container.short_id,
                exit_code,
                success,
                duration,
            )
            return ContainerRunResult(
                exit_code=int(exit_code),
                logs=logs,
                container_id=container.id,
                duration_seconds=duration,
                success=success,
            )

        try:
            return retry_with_backoff(
                _run_container,
                max_attempts=2,
                operation_name="docker agent run",
                retryable=(DockerException,),
            )
        except Exception:
            if container is not None:
                try:
                    logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                    logger.error("Container logs on failure:\n%s", redact_secrets(logs[-4000:]))
                except DockerException:
                    pass
            raise
        finally:
            if container is not None:
                self._cleanup_container(container)

    def run_command(
        self,
        project_root: Path,
        command: str | list[str],
        *,
        working_dir: str = "/workspace",
        timeout_seconds: int = 1800,
    ) -> ContainerRunResult:
        """Run an arbitrary command in the same base image (e.g. tests)."""
        self.ensure_base_image()
        project_root = project_root.resolve()
        volumes = self._build_volumes(project_root)

        if isinstance(command, list):
            cmd = command
        else:
            cmd = ["bash", "-lc", command]

        container_name = f"hyper-cmd-{int(time.time())}"
        start = time.monotonic()
        container: Container | None = None
        try:
            container = self.client.containers.run(
                self.base_image,
                command=cmd,
                name=container_name,
                volumes=volumes,
                working_dir=working_dir,
                detach=True,
                remove=False,
                network_mode=self.network_mode,
            )
            exit_code = self._wait_with_progress(container, timeout_seconds, label="command")
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            return ContainerRunResult(
                exit_code=int(exit_code),
                logs=logs,
                container_id=container.id,
                duration_seconds=time.monotonic() - start,
                success=int(exit_code) == 0,
            )
        finally:
            if container is not None:
                self._cleanup_container(container)

    def _wait_with_progress(
        self, container: Container, timeout_seconds: int, *, label: str = "agent"
    ) -> int:
        """Poll container with periodic progress log lines."""
        deadline = time.monotonic() + timeout_seconds
        last_log_len = 0
        while time.monotonic() < deadline:
            container.reload()
            if container.status in ("exited", "dead"):
                break
            try:
                logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                if len(logs) > last_log_len:
                    for event in extract_progress_events(logs[last_log_len:]):
                        logger.info("[%s] %s", label, redact_secrets(event))
                    last_log_len = len(logs)
            except DockerException:
                pass
            time.sleep(5)

        result = container.wait(timeout=max(1, int(deadline - time.monotonic())))
        return int(result.get("StatusCode", 1))

    def stream_logs(self, container_id: str, tail: int = 100) -> str:
        try:
            container = self.client.containers.get(container_id)
            return container.logs(tail=tail, stdout=True, stderr=True).decode(
                "utf-8", errors="replace"
            )
        except NotFound:
            return ""

    def _build_volumes(self, project_root: Path) -> dict[str, dict[str, str]]:
        volumes: dict[str, dict[str, str]] = {
            str(project_root): {"bind": "/workspace", "mode": "rw"},
        }

        if self.agent_env_path.is_file():
            volumes[str(self.agent_env_path.resolve())] = {
                "bind": "/workspace/.env",
                "mode": "ro",
            }
        else:
            logger.warning(
                "Agent env file not found at %s — Cursor API key may be missing",
                self.agent_env_path,
            )

        if self.ssh_dir.is_dir():
            volumes[str(self.ssh_dir.resolve())] = {
                "bind": "/root/.ssh",
                "mode": "ro",
            }
        else:
            logger.warning("SSH directory %s not found — git push may fail", self.ssh_dir)

        return volumes

    @staticmethod
    def _build_agent_command(prompt: str, *, model: str, yolo: bool) -> list[str]:
        args = [AGENT_BINARY, "--model", model]
        if yolo:
            args.append("--yolo")
        args.extend(["--prompt", prompt])
        return args

    def _cleanup_container(self, container: Container) -> None:
        try:
            container.remove(force=True)
        except DockerException as exc:
            logger.warning("Failed to remove container %s: %s", container.short_id, exc)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    @staticmethod
    def extract_error_signature(logs: str, max_lines: int = 30) -> str:
        """Extract a compact error signature from container logs."""
        lines = logs.strip().splitlines()
        error_lines = [
            line
            for line in lines
            if any(
                token in line.lower()
                for token in ("error", "failed", "exception", "fatal", "traceback")
            )
        ]
        selected = error_lines[-max_lines:] if error_lines else lines[-max_lines:]
        return redact_secrets("\n".join(selected).strip()[:4000])

    @staticmethod
    def is_docker_available() -> bool:
        try:
            client = docker.from_env()
            client.ping()
            client.close()
            return True
        except DockerException:
            return False
