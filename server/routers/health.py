"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server.config import get_agent_env_path
from server.database import get_db
from server.models import Job, JobStatus
from server.schemas import CursorApiKeyStatus, HealthResponse
from server.worker import is_worker_running
from core.agent_env import cursor_api_key_status

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    queued_count = db.query(Job).filter(Job.status == JobStatus.QUEUED).count()
    running_count = db.query(Job).filter(Job.status == JobStatus.RUNNING).count()
    return HealthResponse(
        worker_running=is_worker_running(),
        queued_jobs=queued_count,
        running_jobs=running_count,
        cursor_api_key=CursorApiKeyStatus.model_validate(
            cursor_api_key_status(get_agent_env_path())
        ),
    )
