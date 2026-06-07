"""API call logging and usage statistics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from server.models import ApiCallLog


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def infer_api_source(path: str) -> str:
    if path.startswith("/api/v1/execute-agent"):
        return "n8n"
    if path.startswith("/webhook"):
        return "webhook"
    if path.startswith("/settings") or path.startswith("/stats"):
        return "dashboard"
    return "api"


def log_api_call(
    db: Session,
    *,
    endpoint: str,
    method: str,
    source: str,
    status_code: int,
    project_id: int | None = None,
) -> None:
    db.add(
        ApiCallLog(
            endpoint=endpoint,
            method=method.upper(),
            source=source,
            status_code=status_code,
            project_id=project_id,
        )
    )


def get_api_usage_stats(db: Session, *, recent_limit: int = 10) -> dict:
    now = _utcnow()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = start_of_day - timedelta(days=start_of_day.weekday())

    total = db.query(func.count(ApiCallLog.id)).scalar() or 0
    today = (
        db.query(func.count(ApiCallLog.id))
        .filter(ApiCallLog.created_at >= start_of_day)
        .scalar()
        or 0
    )
    this_week = (
        db.query(func.count(ApiCallLog.id))
        .filter(ApiCallLog.created_at >= start_of_week)
        .scalar()
        or 0
    )

    by_source_rows = (
        db.query(ApiCallLog.source, func.count(ApiCallLog.id))
        .group_by(ApiCallLog.source)
        .all()
    )
    by_endpoint_rows = (
        db.query(ApiCallLog.endpoint, func.count(ApiCallLog.id))
        .group_by(ApiCallLog.endpoint)
        .order_by(func.count(ApiCallLog.id).desc())
        .limit(10)
        .all()
    )

    recent = (
        db.query(ApiCallLog)
        .order_by(ApiCallLog.created_at.desc())
        .limit(recent_limit)
        .all()
    )

    return {
        "total": total,
        "today": today,
        "this_week": this_week,
        "by_source": {source: count for source, count in by_source_rows},
        "by_endpoint": {endpoint: count for endpoint, count in by_endpoint_rows},
        "recent": [
            {
                "id": row.id,
                "endpoint": row.endpoint,
                "method": row.method,
                "source": row.source,
                "status_code": row.status_code,
                "project_id": row.project_id,
                "created_at": row.created_at.isoformat(),
            }
            for row in recent
        ],
    }
