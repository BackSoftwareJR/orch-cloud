"""Custom exception hierarchy for HyperOrchestrator."""

from __future__ import annotations


class HyperOrchestratorError(Exception):
    """Base exception for all orchestrator errors."""

    remediation: str | None = None

    def __init__(self, message: str, *, remediation: str | None = None) -> None:
        super().__init__(message)
        self.remediation = remediation


class ConfigurationError(HyperOrchestratorError):
    """Invalid or missing configuration."""


class HealthCheckError(ConfigurationError):
    """Pre-flight health check failed."""


class SecurityError(HyperOrchestratorError):
    """Security validation failed (URL, prompt, credentials)."""


class DockerOrchestratorError(HyperOrchestratorError):
    """Docker-related orchestration failure."""


class GitError(HyperOrchestratorError):
    """Git operation failure."""


class GitConflictError(GitError):
    """Merge/rebase conflict that cannot be auto-resolved."""


class ProjectNotInitializedError(HyperOrchestratorError):
    """Project repository or workspace directory is missing or not cloned yet."""


class TaskPlanError(HyperOrchestratorError):
    """PRO-level task decomposition or validation failure."""


class RetryExhaustedError(HyperOrchestratorError):
    """All retry attempts failed."""
