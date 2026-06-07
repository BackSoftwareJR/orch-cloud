"""Outbound webhook notifications to backclub.it (or per-project callback URLs)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from server.config import get_webhook_secret
from server.models import Job, JobStatus, Project

logger = logging.getLogger(__name__)

EVENT_MAP = {
    JobStatus.COMPLETED: "job.completed",
    JobStatus.FAILED: "job.failed",
    JobStatus.CANCELLED: "job.cancelled",
}


def _resolve_webhook_url(project: Project) -> str | None:
    settings = project.settings or {}
    url = settings.get("webhook_url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def _sign_payload(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def build_callback_payload(job: Job, project: Project) -> dict[str, Any]:
    event = EVENT_MAP.get(job.status, f"job.{job.status.value.lower()}")
    task_preview = (job.task or "")[:200]
    return {
        "event": event,
        "job_id": job.job_id,
        "project_id": project.id,
        "project_name": project.name,
        "preset": job.preset,
        "level": job.level,
        "status": job.status.value,
        "task_preview": task_preview,
        "error_message": job.error_message,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "log_path": job.logs_path,
        "parent_job_id": job.parent_job_id,
        "thread_root_id": job.thread_root_id,
    }


def _post_webhook_sync(url: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, default=str).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "HyperOrchestrator/2.0"}
    secret = get_webhook_secret()
    if secret:
        headers["X-Orchestrator-Signature"] = _sign_payload(body, secret)

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status >= 400:
            raise urllib.error.HTTPError(url, response.status, "Webhook rejected", response.headers, None)


async def notify_job_finished(job: Job, project: Project) -> None:
    """Fire-and-forget callback when a job reaches a terminal state."""
    url = _resolve_webhook_url(project)
    if not url:
        return
    if job.status not in EVENT_MAP:
        return

    payload = build_callback_payload(job, project)

    try:
        await asyncio.to_thread(_post_webhook_sync, url, payload)
        logger.info("Webhook delivered for job %s → %s", job.job_id[:8], url)
    except Exception:
        logger.exception("Webhook delivery failed for job %s → %s", job.job_id[:8], url)


def schedule_job_webhook(job: Job, project: Project) -> None:
    """Schedule async webhook from sync worker context."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(notify_job_finished(job, project))
    except RuntimeError:
        asyncio.run(notify_job_finished(job, project))
