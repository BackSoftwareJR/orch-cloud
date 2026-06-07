"""Settings endpoints for platform configuration."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from core.agent_env import clear_cursor_api_key, cursor_api_key_status, set_cursor_api_key
from server.config import get_agent_env_path
from server.deps import optional_verify_token
from server.schemas import CursorApiKeyStatus, CursorApiKeyUpdate, SettingsResponse

router = APIRouter(prefix="/settings", tags=["settings"])


def _status_response() -> CursorApiKeyStatus:
    raw = cursor_api_key_status(get_agent_env_path())
    return CursorApiKeyStatus.model_validate(raw)


@router.get("", response_model=SettingsResponse)
def get_settings(
    _: Annotated[None, Depends(optional_verify_token)] = None,
) -> SettingsResponse:
    return SettingsResponse(cursor_api_key=_status_response())


@router.put("/cursor-api-key", response_model=CursorApiKeyStatus)
def update_cursor_api_key(
    payload: CursorApiKeyUpdate,
    _: Annotated[None, Depends(optional_verify_token)] = None,
) -> CursorApiKeyStatus:
    try:
        set_cursor_api_key(payload.api_key, get_agent_env_path())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write agent env file: {exc}",
        ) from exc
    return _status_response()


@router.delete("/cursor-api-key", status_code=204)
def delete_cursor_api_key(
    _: Annotated[None, Depends(optional_verify_token)] = None,
) -> None:
    try:
        clear_cursor_api_key(get_agent_env_path())
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update agent env file: {exc}",
        ) from exc
