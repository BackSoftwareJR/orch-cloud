"""n8n / backclub execute-agent compatibility endpoint."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.presets.registry import resolve_level, resolve_model
from server.api_usage import log_api_call
from server.auth import verify_token
from server.database import get_db
from server.job_service import seed_task_message
from server.models import Job, JobStatus
from server.orchestrator import job_log_path
from server.project_service import get_or_create_project_from_github
from server.schemas import ExecuteAgentRequest, ExecuteAgentResponse
from server.specialist_roles import resolve_preset_from_specialist_role

router = APIRouter(prefix="/api/v1", tags=["n8n"])


def _queue_position(db: Session, job: Job) -> int:
    return (
        db.query(Job)
        .filter(
            Job.status == JobStatus.QUEUED,
            Job.created_at <= job.created_at,
        )
        .count()
    )


@router.post("/execute-agent", response_model=ExecuteAgentResponse)
def execute_agent(
    payload: ExecuteAgentRequest,
    db: Session = Depends(get_db),
    _: Annotated[None, Depends(verify_token)] = None,
) -> ExecuteAgentResponse:
    project = get_or_create_project_from_github(
        db,
        github_url=payload.github_url,
        website_url=payload.website_url,
        crm_project_id=payload.project_id,
        crm_log_url=payload.crm_log_url,
    )

    preset = resolve_preset_from_specialist_role(payload.specialist_role)
    level = resolve_level(preset, "medium").name.lower()
    model = resolve_model(preset, None)

    metadata: dict[str, str] = {}
    if payload.task_id:
        metadata["crm_task_id"] = payload.task_id
    if payload.project_id:
        metadata["crm_project_id"] = payload.project_id
    if payload.website_url:
        metadata["website_url"] = payload.website_url
    if payload.crm_log_url:
        metadata["crm_log_url"] = payload.crm_log_url
    if payload.crm_auth_token:
        metadata["crm_auth_token"] = payload.crm_auth_token
    if payload.specialist_role:
        metadata["specialist_role"] = payload.specialist_role

    job_uuid = str(uuid.uuid4())
    job = Job(
        job_id=job_uuid,
        project_id=project.id,
        task=payload.dedicated_prompt,
        level=level,
        preset=preset,
        model=model,
        status=JobStatus.QUEUED,
        logs_path=str(job_log_path(job_uuid)),
        thread_root_id=job_uuid,
        metadata_=metadata or None,
    )
    db.add(job)
    db.flush()
    seed_task_message(db, job)

    queue_position = _queue_position(db, job)

    log_api_call(
        db,
        endpoint="/api/v1/execute-agent",
        method="POST",
        source="n8n",
        status_code=200,
        project_id=project.id,
    )
    db.commit()
    db.refresh(job)

    return ExecuteAgentResponse(
        status="accepted",
        task_id=str(job.id),
        run_id=job.job_id,
        queue_position=queue_position,
        project_id=project.id,
        orchestrator_job_id=job.job_id,
    )
