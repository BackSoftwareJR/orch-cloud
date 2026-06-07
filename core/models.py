"""Pydantic models for HyperOrchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum, IntEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from core.security import sanitize_task_prompt, validate_repo_url


class TaskLevel(IntEnum):
    """Execution depth for orchestrated tasks."""

    FAST = 1
    MEDIUM = 2
    PRO = 3

    @classmethod
    def from_value(cls, value: str | int) -> TaskLevel:
        mapping = {
            "1": cls.FAST,
            "2": cls.MEDIUM,
            "3": cls.PRO,
            "fast": cls.FAST,
            "medium": cls.MEDIUM,
            "pro": cls.PRO,
            "level1": cls.FAST,
            "level2": cls.MEDIUM,
            "level3": cls.PRO,
            "l1": cls.FAST,
            "l2": cls.MEDIUM,
            "l3": cls.PRO,
        }
        key = str(value).lower().strip()
        if key not in mapping:
            raise ValueError(
                f"Invalid task level '{value}'. Use 1/2/3, fast/medium/pro, or level1/level2/level3."
            )
        return mapping[key]


class AgentPreset(str, Enum):
    """Specialized agent role for orchestrated tasks."""

    GENERAL = "general"
    UX = "ux"
    BACKEND = "backend"
    BUGFIX = "bugfix"

    @classmethod
    def from_value(cls, value: str | AgentPreset | None) -> AgentPreset:
        if isinstance(value, cls):
            return value
        if value is None or not str(value).strip():
            return cls.GENERAL
        raw = str(value).strip()
        if raw.startswith("AgentPreset."):
            raw = raw.split(".", 1)[1]
        key = raw.lower()
        for member in cls:
            if member.value == key or member.name.lower() == key:
                return member
        raise ValueError(
            f"Invalid preset '{value}'. Use: {', '.join(m.value for m in cls)}."
        )

    @classmethod
    def to_value(cls, value: str | AgentPreset | None) -> str:
        """Return canonical CLI/DB preset string (e.g. ``general``)."""
        return cls.from_value(value).value


class TaskRequest(BaseModel):
    """Validated input for an orchestration run."""

    repo_url: str = Field(..., min_length=1, description="Git repository URL")
    task: str = Field(..., min_length=1, description="Natural-language task description")
    level: TaskLevel = TaskLevel.MEDIUM
    preset: AgentPreset = AgentPreset.GENERAL
    model: str | None = Field(default=None, description="Cursor agent model slug override")
    work_dir: str | None = Field(default=None, description="Local clone directory")
    max_debug_retries: int = Field(default=6, ge=1, le=10)
    openai_model: str = Field(default="gpt-4o-mini")
    dry_run: bool = Field(default=False, description="Validate and plan without executing agents")
    json_logs: bool = Field(default=False, description="Emit structured JSON logs")
    report_dir: str | None = Field(default=None, description="Directory for run summary JSON")

    @field_validator("repo_url")
    @classmethod
    def validate_repo(cls, value: str) -> str:
        return validate_repo_url(value)

    @field_validator("task")
    @classmethod
    def validate_task(cls, value: str) -> str:
        return sanitize_task_prompt(value)


FrameworkType = Literal["laravel", "nextjs", "unknown"]


class AtomicTask(BaseModel):
    """Single step in a PRO-level multi-task plan."""

    id: int
    title: str
    description: str
    validation_command: str | None = None
    depends_on: list[int] = Field(default_factory=list)


class TaskPlan(BaseModel):
    """PRO-level decomposed task plan."""

    tasks: list[AtomicTask]
    summary: str = ""


class LearnedPattern(BaseModel):
    """Recorded error/solution pair from past runs."""

    id: int | None = None
    project_key: str
    error_pattern: str
    solution_pattern: str
    task_summary: str = ""
    failure_count: int = 0
    is_global: bool = False
    relevance_score: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnalysisResult(BaseModel):
    """Output from a framework analyzer."""

    framework: FrameworkType
    summary: str
    details: dict[str, object] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class OrchestrationResult(BaseModel):
    """Final outcome of an orchestration run."""

    success: bool
    level: TaskLevel
    message: str
    pushed_to_staging: bool = False
    tasks_completed: int = 0
    tests_passed: bool | None = None
    tests_skipped: bool = False
    report_path: Path | None = None
    correlation_id: str | None = None
