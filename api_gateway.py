"""Async API gateway for HyperOrchestrator webhook triggers."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from core.exceptions import SecurityError
from core.models import TaskLevel
from core.security import sanitize_task_prompt, validate_repo_url

logger = logging.getLogger(__name__)

# Dev-only default — override with ORCHESTRATOR_API_TOKEN or WEBHOOK_TOKEN in production.
DEFAULT_DEV_TOKEN = "dev-orchestrator-token-change-me"

JOBS_DIR = Path.home() / ".hyper-orchestrator" / "jobs"
PROJECT_ROOT = Path(__file__).resolve().parent
LOG_TAIL_LINES = 50


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


_jobs: dict[str, dict[str, object]] = {}


def _get_api_token() -> str:
    return (
        os.environ.get("ORCHESTRATOR_API_TOKEN")
        or os.environ.get("WEBHOOK_TOKEN")
        or DEFAULT_DEV_TOKEN
    )


def _resolve_orchestrator_cmd() -> list[str]:
    """Return command prefix for hyper-orchestrator CLI."""
    venv_bin = PROJECT_ROOT / ".venv" / "bin" / "hyper-orchestrator"
    if venv_bin.is_file():
        return [str(venv_bin)]
    if shutil.which("hyper-orchestrator"):
        return ["hyper-orchestrator"]
    return [sys.executable, "-m", "core.main"]


def verify_token(
    authorization: Annotated[str | None, Header()] = None,
    x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None,
) -> None:
    expected = _get_api_token()
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_token:
        token = x_api_token.strip()

    if not token or token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


class TriggerTaskRequest(BaseModel):
    repo_url: str = Field(..., min_length=1)
    task: str = Field(..., min_length=1)
    level: str | int = Field(default="medium")

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


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    log_path: str
    log_tail: str | None = None
    exit_code: int | None = None
    created_at: str | None = None
    finished_at: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"


def _read_log_tail(log_path: Path, max_lines: int = LOG_TAIL_LINES) -> str | None:
    if not log_path.is_file():
        return None
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    return "\n".join(lines[-max_lines:]) if lines else ""


def _run_orchestrator_job(job_id: str, repo_url: str, task: str, level: str) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = JOBS_DIR / f"{job_id}.log"

    _jobs[job_id]["status"] = JobStatus.RUNNING
    _jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

    cmd = _resolve_orchestrator_cmd() + [
        "--repo",
        repo_url,
        "--task",
        task,
        "--level",
        level,
        "--json-log",
    ]

    logger.info("Starting job %s: %s", job_id, " ".join(cmd))

    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            log_file.write(f"Command: {' '.join(cmd)}\n")
            log_file.write(f"Started: {_jobs[job_id]['started_at']}\n\n")
            log_file.flush()

            with subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            ) as proc:
                assert proc.stdout is not None
                for line in proc.stdout:
                    log_file.write(line)
                    log_file.flush()
                exit_code = proc.wait()

            log_file.write(f"\n\nExit code: {exit_code}\n")

        _jobs[job_id]["exit_code"] = exit_code
        _jobs[job_id]["status"] = JobStatus.COMPLETED if exit_code == 0 else JobStatus.FAILED
    except Exception as exc:
        logger.exception("Job %s failed with exception", job_id)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"\nException: {exc}\n")
        _jobs[job_id]["status"] = JobStatus.FAILED
        _jobs[job_id]["exit_code"] = -1
    finally:
        _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()


app = FastAPI(
    title="HyperOrchestrator API Gateway",
    version="1.0.0",
)


@app.on_event("startup")
def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    if _get_api_token() == DEFAULT_DEV_TOKEN:
        logger.warning(
            "Using dev-only API token — set ORCHESTRATOR_API_TOKEN or WEBHOOK_TOKEN in production"
        )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/webhook/trigger-task", response_model=TriggerTaskResponse)
def trigger_task(
    request: TriggerTaskRequest,
    background_tasks: BackgroundTasks,
    _: Annotated[None, Depends(verify_token)],
) -> TriggerTaskResponse:
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = JOBS_DIR / f"{job_id}.log"

    _jobs[job_id] = {
        "status": JobStatus.QUEUED,
        "log_path": str(log_path),
        "created_at": now,
        "started_at": None,
        "finished_at": None,
        "exit_code": None,
    }

    logger.info("Queued job %s for repo=%s level=%s", job_id, request.repo_url, request.level)

    background_tasks.add_task(
        _run_orchestrator_job,
        job_id,
        request.repo_url,
        request.task,
        request.level,
    )

    return TriggerTaskResponse(job_id=job_id, status="queued")


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    _: Annotated[None, Depends(verify_token)],
) -> JobStatusResponse:
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _jobs[job_id]
    log_path = Path(str(job["log_path"]))

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],  # type: ignore[arg-type]
        log_path=str(log_path),
        log_tail=_read_log_tail(log_path),
        exit_code=job.get("exit_code"),  # type: ignore[arg-type]
        created_at=job.get("created_at"),  # type: ignore[arg-type]
        finished_at=job.get("finished_at"),  # type: ignore[arg-type]
    )
