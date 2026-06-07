"""HTTP middleware for cross-cutting platform concerns."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from server.api_usage import infer_api_source, log_api_call
from server.database import SessionLocal

_TRACKED_PREFIXES = ("/api/v1/", "/webhook/", "/projects/", "/jobs", "/settings")


class ApiUsageMiddleware(BaseHTTPMiddleware):
    """Persist lightweight API call metrics for dashboard stats."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path.startswith("/api/v1/execute-agent"):
            return await call_next(request)
        should_track = any(path.startswith(prefix) for prefix in _TRACKED_PREFIXES)
        if not should_track or request.method == "OPTIONS":
            return await call_next(request)

        response = await call_next(request)
        db = SessionLocal()
        try:
            log_api_call(
                db,
                endpoint=path,
                method=request.method,
                source=infer_api_source(path),
                status_code=response.status_code,
            )
            db.commit()
        finally:
            db.close()
        return response
