"""Pydantic request/response schemas for the platform API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.exceptions import SecurityError
from core.models import AgentPreset, TaskLevel
from core.presets.registry import resolve_level, validate_model
from core.security import sanitize_task_prompt, validate_repo_url
from server.models import JobStatus


def _coerce_optional_str(value: object) -> str | None:
    """Accept CRM/n8n values that arrive as numbers or other scalars."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value)


class CursorApiKeyStatus(BaseModel):
    configured: bool
    masked_preview: str | None = None
    updated_at: datetime | None = None
    source_path: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    worker_running: bool = True
    queued_jobs: int = 0
    running_jobs: int = 0
    cursor_api_key: CursorApiKeyStatus | None = None


class SettingsResponse(BaseModel):
    cursor_api_key: CursorApiKeyStatus


class CursorApiKeyUpdate(BaseModel):
    api_key: str = Field(..., min_length=8, max_length=512)


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    repo_url: str = Field(..., min_length=1)
    settings: dict | None = None

    @field_validator("repo_url")
    @classmethod
    def validate_repo(cls, value: str) -> str:
        try:
            return validate_repo_url(value)
        except SecurityError as exc:
            raise ValueError(str(exc)) from exc


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    repo_url: str | None = None
    settings: dict | None = None

    @field_validator("repo_url")
    @classmethod
    def validate_repo(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            return validate_repo_url(value)
        except SecurityError as exc:
            raise ValueError(str(exc)) from exc


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    repo_url: str
    settings: dict | None
    created_at: datetime
    updated_at: datetime


class JobCreate(BaseModel):
    task: str = Field(..., min_length=1)
    level: str | int | None = Field(default=None)
    preset: str = Field(default="general")
    model: str | None = Field(default=None)

    @field_validator("task")
    @classmethod
    def validate_task(cls, value: str) -> str:
        try:
            return sanitize_task_prompt(value)
        except SecurityError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("preset")
    @classmethod
    def validate_preset(cls, value: str) -> str:
        try:
            return AgentPreset.from_value(value).value
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("level")
    @classmethod
    def validate_level(cls, value: str | int | None) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            TaskLevel.from_value(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return str(value).strip()

    @field_validator("model")
    @classmethod
    def validate_model_field(cls, value: str | None) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            return validate_model(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class PresetResponse(BaseModel):
    id: str
    label: str
    description: str
    default_level: str
    default_model: str
    capabilities: list[str]
    version: str = "2.0"


class PresetDetailResponse(PresetResponse):
    example_payload: dict[str, str]
    forbidden_actions: list[str]
    quality_checklist: list[str] = Field(default_factory=list)
    output_expectations: str = ""


class TriggerTaskRequest(BaseModel):
    repo_url: str = Field(..., min_length=1)
    task: str = Field(..., min_length=1)
    level: str | int | None = Field(default=None)
    preset: str = Field(default="general")
    model: str | None = Field(default=None)
    project_id: int | None = None

    @field_validator("repo_url")
    @classmethod
    def validate_repo(cls, value: str) -> str:
        try:
            return validate_repo_url(value)
        except SecurityError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("task")
    @classmethod
    def validate_task(cls, value: str) -> str:
        try:
            return sanitize_task_prompt(value)
        except SecurityError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("preset")
    @classmethod
    def validate_preset(cls, value: str) -> str:
        try:
            return AgentPreset.from_value(value).value
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("level")
    @classmethod
    def validate_level(cls, value: str | int | None) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            TaskLevel.from_value(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return str(value).strip()

    @field_validator("model")
    @classmethod
    def validate_model_field(cls, value: str | None) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            return validate_model(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class TriggerTaskResponse(BaseModel):
    job_id: str
    status: str = "queued"
    project_id: int


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    project_id: int
    status: JobStatus
    level: str
    preset: str
    model: str | None = None
    task: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    logs_path: str | None
    error_message: str | None
    parent_job_id: str | None = None
    thread_root_id: str | None = None
    log_tail: str | None = None
    can_auto_fix: bool = False


class ModelResponse(BaseModel):
    slug: str
    label: str
    tier: str
    description: str


class JobContinueRequest(BaseModel):
    message: str = Field(..., min_length=1)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        try:
            return sanitize_task_prompt(value)
        except SecurityError as exc:
            raise ValueError(str(exc)) from exc


class JobMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    role: str
    content: str
    created_at: datetime


class JobStatusResponse(BaseModel):
    """Backward-compatible job status response for webhook clients."""

    job_id: str
    status: str
    log_path: str | None
    log_tail: str | None = None
    exit_code: int | None = None
    created_at: str | None = None
    finished_at: str | None = None


class ExecuteAgentRequest(BaseModel):
    """n8n / backclub CRM payload for Hyper-bs workflow."""

    dedicated_prompt: str = Field(..., min_length=1)
    exact_prompt: bool = Field(
        default=False,
        description="When true, preserve dedicated_prompt verbatim (no trim/sanitize).",
    )
    github_url: str = Field(..., min_length=1)
    specialist_role: str | None = Field(default=None)
    task_id: str | None = Field(
        default=None,
        description="CRM task id (numeric) or workspace_agent_{id}",
    )
    project_id: str | None = Field(default=None, description="External CRM project id")
    website_url: str | None = None
    crm_log_url: str | None = None
    crm_auth_token: str | None = None
    callback_url: str | None = Field(
        default=None,
        description="CRM task-events webhook (append step/event)",
    )
    callback_status_url: str | None = Field(
        default=None,
        description="CRM status webhook (n8n_status / progress updates)",
    )
    callback_completed_url: str | None = Field(
        default=None,
        description="CRM completed webhook",
    )
    callback_task_log_url: str | None = Field(
        default=None,
        description="CRM task-log webhook (streaming log lines)",
    )
    callback_close_task_url: str | None = Field(
        default=None,
        description="CRM close-task webhook",
    )
    callback_auth_header: str | None = Field(
        default=None,
        description="Auth header name for CRM callbacks (e.g. authbs)",
    )
    callback_n8n_proxy_url: str | None = Field(
        default=None,
        description="n8n Callback Receiver webhook — CRM callbacks are routed here instead of direct",
    )

    @field_validator(
        "specialist_role",
        "task_id",
        "project_id",
        "website_url",
        "crm_log_url",
        "crm_auth_token",
        "callback_url",
        "callback_status_url",
        "callback_completed_url",
        "callback_task_log_url",
        "callback_close_task_url",
        "callback_auth_header",
        "callback_n8n_proxy_url",
        mode="before",
    )
    @classmethod
    def coerce_crm_fields(cls, value: object) -> str | None:
        return _coerce_optional_str(value)

    @field_validator("dedicated_prompt", mode="before")
    @classmethod
    def coerce_prompt(cls, value: object) -> str:
        if isinstance(value, str):
            if not value:
                raise ValueError("dedicated_prompt is required")
            return value
        coerced = _coerce_optional_str(value)
        if not coerced:
            raise ValueError("dedicated_prompt is required")
        return coerced

    @field_validator("github_url", mode="before")
    @classmethod
    def coerce_github(cls, value: object) -> str:
        coerced = _coerce_optional_str(value)
        if not coerced:
            raise ValueError("github_url is required")
        return coerced

    @model_validator(mode="after")
    def validate_prompt_exact(self) -> "ExecuteAgentRequest":
        try:
            if self.exact_prompt:
                if not self.dedicated_prompt:
                    raise SecurityError(
                        "Task description is empty.",
                        remediation="Provide dedicated_prompt.",
                    )
                if "\x00" in self.dedicated_prompt:
                    object.__setattr__(
                        self,
                        "dedicated_prompt",
                        self.dedicated_prompt.replace("\x00", ""),
                    )
            else:
                object.__setattr__(
                    self,
                    "dedicated_prompt",
                    sanitize_task_prompt(self.dedicated_prompt),
                )
        except SecurityError as exc:
            raise ValueError(str(exc)) from exc
        return self

    @field_validator("github_url")
    @classmethod
    def validate_github(cls, value: str) -> str:
        try:
            return validate_repo_url(value)
        except SecurityError as exc:
            raise ValueError(str(exc)) from exc


class ExecuteAgentResponse(BaseModel):
    status: str = "accepted"
    task_id: str
    run_id: str
    queue_position: int
    project_id: int
    orchestrator_job_id: str


class ApiUsageRecentCall(BaseModel):
    id: int
    endpoint: str
    method: str
    source: str
    status_code: int
    project_id: int | None
    created_at: str


class ApiUsageStatsResponse(BaseModel):
    total: int
    today: int
    this_week: int
    by_source: dict[str, int]
    by_endpoint: dict[str, int]
    recent: list[ApiUsageRecentCall]
