"""Outbound webhook notifications to CRM (n8n callbacks) and project webhooks."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from server.config import (
    get_crm_callback_n8n_auth_header,
    get_crm_callback_n8n_auth_value,
    get_crm_callback_n8n_webhook_url,
    get_webhook_secret,
)
from server.models import Job, JobStatus, Project

logger = logging.getLogger(__name__)

EVENT_MAP = {
    JobStatus.COMPLETED: "job.completed",
    JobStatus.FAILED: "job.failed",
    JobStatus.CANCELLED: "job.cancelled",
}

CRM_STATUS_MAP = {
    JobStatus.QUEUED: "queued",
    JobStatus.RUNNING: "running",
    JobStatus.COMPLETED: "completed",
    JobStatus.FAILED: "failed",
    JobStatus.CANCELLED: "cancelled",
}

METADATA_CALLBACK_KEYS = (
    "crm_task_id",
    "crm_project_id",
    "callback_status_url",
    "callback_completed_url",
    "callback_task_log_url",
    "callback_url",
    "callback_close_task_url",
    "callback_auth_header",
    "crm_auth_token",
    "callback_n8n_proxy_url",
    "exact_prompt",
    "website_url",
    "crm_log_url",
)


@dataclass(frozen=True)
class CrmCallbackConfig:
    task_id: str | None
    project_id: str | None
    status_url: str | None
    completed_url: str | None
    task_log_url: str | None
    events_url: str | None
    close_task_url: str | None
    auth_header: str | None
    auth_value: str | None
    n8n_proxy_url: str | None = None


def build_job_metadata_from_execute_agent(payload: Any) -> dict[str, str]:
    """Persist CRM/n8n callback fields on the job for the worker lifecycle."""
    metadata: dict[str, str] = {}
    if payload.task_id:
        metadata["crm_task_id"] = str(payload.task_id)
    if payload.project_id:
        metadata["crm_project_id"] = str(payload.project_id)
    if payload.website_url:
        metadata["website_url"] = payload.website_url
    if payload.crm_log_url:
        metadata["crm_log_url"] = payload.crm_log_url
    if payload.crm_auth_token:
        metadata["crm_auth_token"] = payload.crm_auth_token
    if payload.specialist_role:
        metadata["specialist_role"] = payload.specialist_role
    if payload.callback_url:
        metadata["callback_url"] = payload.callback_url
    if payload.callback_status_url:
        metadata["callback_status_url"] = payload.callback_status_url
    if payload.callback_completed_url:
        metadata["callback_completed_url"] = payload.callback_completed_url
    if payload.callback_task_log_url:
        metadata["callback_task_log_url"] = payload.callback_task_log_url
    if payload.callback_close_task_url:
        metadata["callback_close_task_url"] = payload.callback_close_task_url
    if payload.callback_auth_header:
        metadata["callback_auth_header"] = payload.callback_auth_header
    if getattr(payload, "callback_n8n_proxy_url", None):
        metadata["callback_n8n_proxy_url"] = payload.callback_n8n_proxy_url
    if payload.exact_prompt:
        metadata["exact_prompt"] = "true"
    return metadata


def parse_crm_callbacks(metadata: dict | None) -> CrmCallbackConfig | None:
    if not metadata:
        return None
    task_id = metadata.get("crm_task_id")
    if not task_id:
        return None
    proxy_url = _clean_url(metadata.get("callback_n8n_proxy_url")) or get_crm_callback_n8n_webhook_url()
    return CrmCallbackConfig(
        task_id=str(task_id),
        project_id=metadata.get("crm_project_id"),
        status_url=_clean_url(metadata.get("callback_status_url")),
        completed_url=_clean_url(metadata.get("callback_completed_url")),
        task_log_url=_clean_url(metadata.get("callback_task_log_url")),
        events_url=_clean_url(metadata.get("callback_url")),
        close_task_url=_clean_url(metadata.get("callback_close_task_url")),
        auth_header=_clean_str(metadata.get("callback_auth_header")),
        auth_value=_clean_str(metadata.get("crm_auth_token")),
        n8n_proxy_url=proxy_url,
    )


def _clean_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or cleaned == "=":
        return None
    if not cleaned.startswith(("http://", "https://")):
        return None
    return cleaned


def _clean_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _resolve_webhook_url(project: Project) -> str | None:
    settings = project.settings or {}
    url = settings.get("webhook_url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def _sign_payload(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _build_auth_headers(config: CrmCallbackConfig | None, body: bytes) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "User-Agent": "HyperOrchestrator/2.0"}
    if config and config.auth_header and config.auth_value:
        headers[config.auth_header] = config.auth_value
    secret = get_webhook_secret()
    if secret:
        headers["X-Orchestrator-Signature"] = _sign_payload(body, secret)
    return headers


def _build_n8n_proxy_auth_config() -> CrmCallbackConfig | None:
    header = get_crm_callback_n8n_auth_header()
    value = get_crm_callback_n8n_auth_value()
    if not header or not value:
        return None
    return CrmCallbackConfig(
        task_id=None,
        project_id=None,
        status_url=None,
        completed_url=None,
        task_log_url=None,
        events_url=None,
        close_task_url=None,
        auth_header=header,
        auth_value=value,
        n8n_proxy_url=None,
    )


def _prepare_crm_delivery(
    target_url: str,
    payload: dict[str, Any],
    config: CrmCallbackConfig | None,
    callback_type: str,
) -> tuple[str, dict[str, Any], CrmCallbackConfig | None]:
    """When n8n proxy is configured, wrap CRM callback for the Callback Receiver workflow."""
    proxy_url = config.n8n_proxy_url if config else None
    if not proxy_url:
        proxy_url = get_crm_callback_n8n_webhook_url()
    if not proxy_url:
        return target_url, payload, config

    envelope: dict[str, Any] = {
        "callback_type": callback_type,
        "target_url": target_url,
        "callback_auth_header": config.auth_header if config else None,
        "crm_auth_token": config.auth_value if config else None,
        **payload,
        "payload": payload,
    }
    if callback_type == "completed":
        envelope["callback_completed_url"] = target_url
    elif callback_type == "status":
        envelope["callback_status_url"] = target_url
    elif callback_type == "close-task":
        envelope["callback_close_task_url"] = target_url
    elif callback_type == "task-log":
        envelope["callback_task_log_url"] = target_url
    elif callback_type == "task-events":
        envelope["callback_url"] = target_url

    proxy_auth = _build_n8n_proxy_auth_config()
    return proxy_url, envelope, proxy_auth or config


def _post_webhook_sync(
    url: str,
    payload: dict[str, Any],
    config: CrmCallbackConfig | None = None,
) -> None:
    body = json.dumps(payload, default=str).encode("utf-8")
    headers = _build_auth_headers(config, body)
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status >= 400:
            raise urllib.error.HTTPError(url, response.status, "Webhook rejected", response.headers, None)


def build_callback_payload(job: Job, project: Project) -> dict[str, Any]:
    event = EVENT_MAP.get(job.status, f"job.{job.status.value.lower()}")
    task_preview = (job.task or "")[:200]
    metadata = job.metadata_ or {}
    payload: dict[str, Any] = {
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
    if metadata.get("crm_task_id"):
        payload["task_id"] = metadata["crm_task_id"]
    if metadata.get("crm_project_id"):
        payload["crm_project_id"] = metadata["crm_project_id"]
    return payload


def build_crm_status_payload(
    job: Job,
    *,
    message: str | None = None,
    progress: int | None = None,
) -> dict[str, Any]:
    metadata = job.metadata_ or {}
    crm_status = CRM_STATUS_MAP.get(job.status, job.status.value.lower())
    payload: dict[str, Any] = {
        "task_id": metadata.get("crm_task_id"),
        "project_id": metadata.get("crm_project_id"),
        "status": crm_status,
        "n8n_status": crm_status,
        "run_id": job.job_id,
        "orchestrator_job_id": job.job_id,
        "message": message or f"Job {crm_status}",
    }
    if progress is not None:
        payload["progress"] = max(0, min(100, progress))
    if job.error_message:
        payload["error"] = job.error_message
    return payload


def build_crm_completed_payload(job: Job) -> dict[str, Any]:
    metadata = job.metadata_ or {}
    succeeded = job.status == JobStatus.COMPLETED
    payload: dict[str, Any] = {
        "task_id": metadata.get("crm_task_id"),
        "project_id": metadata.get("crm_project_id"),
        "status": "completed" if succeeded else "failed",
        "run_id": job.job_id,
        "orchestrator_job_id": job.job_id,
        "message": (
            "Agent completed successfully"
            if succeeded
            else (job.error_message or "Agent failed")
        ),
    }
    if job.error_message:
        payload["error"] = job.error_message
    if succeeded:
        payload["progress"] = 100
        payload["result"] = {
            "job_id": job.job_id,
            "log_path": job.logs_path,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }
    return payload


def build_crm_log_payload(
    job_id: str,
    metadata: dict | None,
    line: str,
    *,
    step_key: str | None = None,
) -> dict[str, Any]:
    meta = metadata or {}
    trimmed = line.rstrip("\n")
    return {
        "task_id": meta.get("crm_task_id"),
        "project_id": meta.get("crm_project_id"),
        "run_id": job_id,
        "step_key": step_key or f"log_{int(time.time() * 1000)}",
        "title": "Agent Output",
        "message": trimmed[:4000],
        "log_message": trimmed[:4000],
        "status": "completed",
    }


def build_crm_event_payload(
    job: Job,
    *,
    step_key: str,
    title: str,
    message: str,
    status: str = "completed",
) -> dict[str, Any]:
    metadata = job.metadata_ or {}
    return {
        "task_id": metadata.get("crm_task_id"),
        "project_id": metadata.get("crm_project_id"),
        "run_id": job.job_id,
        "step_key": step_key,
        "title": title,
        "message": message,
        "status": status,
    }


async def post_crm_callback(
    url: str,
    payload: dict[str, Any],
    config: CrmCallbackConfig | None,
    job_id: str,
    label: str,
) -> None:
    delivery_url, delivery_payload, delivery_config = _prepare_crm_delivery(
        url, payload, config, label
    )
    via_proxy = delivery_url != url
    try:
        await asyncio.to_thread(_post_webhook_sync, delivery_url, delivery_payload, delivery_config)
        if via_proxy:
            logger.info(
                "CRM %s callback proxied via n8n for job %s → %s (target %s)",
                label,
                job_id[:8],
                delivery_url,
                url,
            )
        else:
            logger.info("CRM %s callback delivered for job %s → %s", label, job_id[:8], url)
    except Exception:
        if via_proxy:
            logger.exception(
                "CRM %s callback failed via n8n proxy for job %s → %s (target %s)",
                label,
                job_id[:8],
                delivery_url,
                url,
            )
        else:
            logger.exception("CRM %s callback failed for job %s → %s", label, job_id[:8], url)


async def notify_crm_status(
    job: Job,
    *,
    message: str | None = None,
    progress: int | None = None,
) -> None:
    config = parse_crm_callbacks(job.metadata_)
    if config is None or not config.status_url:
        return
    payload = build_crm_status_payload(job, message=message, progress=progress)
    await post_crm_callback(config.status_url, payload, config, job.job_id, "status")


async def notify_crm_completed(job: Job) -> None:
    config = parse_crm_callbacks(job.metadata_)
    if config is None:
        return
    payload = build_crm_completed_payload(job)
    if config.completed_url:
        await post_crm_callback(config.completed_url, payload, config, job.job_id, "completed")
    if job.status == JobStatus.COMPLETED and config.close_task_url:
        close_payload = {
            **payload,
            "message": payload.get("message", "Task closed by orchestrator"),
        }
        await post_crm_callback(config.close_task_url, close_payload, config, job.job_id, "close-task")


async def notify_crm_log_line(job_id: str, metadata: dict | None, line: str) -> None:
    config = parse_crm_callbacks(metadata)
    if config is None:
        return
    trimmed = line.strip()
    if not trimmed:
        return
    payload = build_crm_log_payload(job_id, metadata, trimmed)
    if config.task_log_url:
        await post_crm_callback(config.task_log_url, payload, config, job_id, "task-log")
    elif config.events_url:
        await post_crm_callback(config.events_url, payload, config, job_id, "task-events")


async def notify_crm_event(
    job: Job,
    *,
    step_key: str,
    title: str,
    message: str,
    status: str = "completed",
) -> None:
    config = parse_crm_callbacks(job.metadata_)
    if config is None or not config.events_url:
        return
    payload = build_crm_event_payload(
        job,
        step_key=step_key,
        title=title,
        message=message,
        status=status,
    )
    await post_crm_callback(config.events_url, payload, config, job.job_id, "task-events")


def schedule_crm_status(job: Job, *, message: str | None = None, progress: int | None = None) -> None:
    config = parse_crm_callbacks(job.metadata_)
    if config is None or not config.status_url:
        return
    payload = build_crm_status_payload(job, message=message, progress=progress)
    _schedule_callback(config.status_url, payload, config, job.job_id, "status")


def schedule_crm_completed(job: Job) -> None:
    config = parse_crm_callbacks(job.metadata_)
    if config is None:
        return
    payload = build_crm_completed_payload(job)
    if config.completed_url:
        _schedule_callback(config.completed_url, payload, config, job.job_id, "completed")
    if job.status == JobStatus.COMPLETED and config.close_task_url:
        close_payload = {
            **payload,
            "message": payload.get("message", "Task closed by orchestrator"),
        }
        _schedule_callback(config.close_task_url, close_payload, config, job.job_id, "close-task")


def schedule_crm_log_line(job_id: str, metadata: dict | None, line: str) -> None:
    config = parse_crm_callbacks(metadata)
    if config is None:
        return
    trimmed = line.strip()
    if not trimmed:
        return
    payload = build_crm_log_payload(job_id, metadata, trimmed)
    if config.task_log_url:
        _schedule_callback(config.task_log_url, payload, config, job_id, "task-log")
    elif config.events_url:
        _schedule_callback(config.events_url, payload, config, job_id, "task-events")


def _schedule_callback(
    url: str,
    payload: dict[str, Any],
    config: CrmCallbackConfig,
    job_id: str,
    label: str,
) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(post_crm_callback(url, payload, config, job_id, label))
    except RuntimeError:
        asyncio.run(post_crm_callback(url, payload, config, job_id, label))


async def notify_job_finished_with_payload(
    url: str,
    payload: dict[str, Any],
    job_id: str,
    config: CrmCallbackConfig | None = None,
) -> None:
    """Fire-and-forget callback using a pre-built payload (safe after DB session closes)."""
    try:
        await asyncio.to_thread(_post_webhook_sync, url, payload, config)
        logger.info("Webhook delivered for job %s → %s", job_id[:8], url)
    except Exception:
        logger.exception("Webhook delivery failed for job %s → %s", job_id[:8], url)


async def notify_job_finished(job: Job, project: Project) -> None:
    """Fire-and-forget callback when a job reaches a terminal state."""
    metadata = job.metadata_ or {}
    crm_log_url = metadata.get("crm_log_url")
    url = crm_log_url if isinstance(crm_log_url, str) and crm_log_url.strip() else _resolve_webhook_url(project)
    if not url:
        return
    if job.status not in EVENT_MAP:
        return

    config = parse_crm_callbacks(metadata)
    payload = build_callback_payload(job, project)
    await notify_job_finished_with_payload(url.strip(), payload, job.job_id, config)


def schedule_job_webhook(job: Job, project: Project) -> None:
    """Schedule async webhook from sync worker context."""
    metadata = job.metadata_ or {}
    crm_log_url = metadata.get("crm_log_url")
    url = crm_log_url if isinstance(crm_log_url, str) and crm_log_url.strip() else _resolve_webhook_url(project)
    if not url or job.status not in EVENT_MAP:
        return
    config = parse_crm_callbacks(metadata)
    payload = build_callback_payload(job, project)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(notify_job_finished_with_payload(url.strip(), payload, job.job_id, config))
    except RuntimeError:
        asyncio.run(notify_job_finished_with_payload(url.strip(), payload, job.job_id, config))
