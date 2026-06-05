"""Pydantic request/response schemas for the platform API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.exceptions import SecurityError
from core.models import TaskLevel
from core.security import sanitize_task_prompt, validate_repo_url
from server.models import JobStatus


class HealthResponse(BaseModel):
    status: str = "ok"
    worker_running: bool = True
    queued_jobs: int = 0
    running_jobs: int = 0


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
    level: str | int = Field(default="medium")

    @field_validator("task")
    @classmethod
    def validate_task(cls, value: str) -> str:
        try:
            return sanitize_task_prompt(value)
        except SecurityError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("level")
    @classmethod
    def validate_level(cls, value: str | int) -> str:
        try:
            TaskLevel.from_value(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return str(value).strip()


class TriggerTaskRequest(BaseModel):
    repo_url: str = Field(..., min_length=1)
    task: str = Field(..., min_length=1)
    level: str | int = Field(default="medium")
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

    @field_validator("level")
    @classmethod
    def validate_level(cls, value: str | int) -> str:
        try:
            TaskLevel.from_value(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return str(value).strip()


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
    task: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    logs_path: str | None
    error_message: str | None
    log_tail: str | None = None


class JobStatusResponse(BaseModel):
    """Backward-compatible job status response for webhook clients."""

    job_id: str
    status: str
    log_path: str | None
    log_tail: str | None = None
    exit_code: int | None = None
    created_at: str | None = None
    finished_at: str | None = None
