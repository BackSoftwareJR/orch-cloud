"""API token authentication."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from server.config import get_api_token


def _normalize_token(value: str | None) -> str | None:
    if value is None:
        return None
    token = value.strip().strip('"').strip("'").strip("\r\n")
    return token or None


def verify_token(
    authorization: Annotated[str | None, Header()] = None,
    x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    expected = get_api_token()
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = _normalize_token(authorization[7:])
    elif x_api_key:
        token = _normalize_token(x_api_key)
    elif x_api_token:
        token = _normalize_token(x_api_token)

    if not token or token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")
