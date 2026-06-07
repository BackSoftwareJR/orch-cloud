"""API token authentication."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from server.config import get_api_token


def verify_token(
    authorization: Annotated[str | None, Header()] = None,
    x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    expected = get_api_token()
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()
    elif x_api_token:
        token = x_api_token.strip()

    if not token or token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")
