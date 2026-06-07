"""API usage statistics endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server.api_usage import get_api_usage_stats
from server.database import get_db
from server.deps import optional_verify_token
from server.schemas import ApiUsageStatsResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/api-usage", response_model=ApiUsageStatsResponse)
def api_usage(
    db: Session = Depends(get_db),
    _: Annotated[None, Depends(optional_verify_token)] = None,
) -> ApiUsageStatsResponse:
    return ApiUsageStatsResponse.model_validate(get_api_usage_stats(db))
