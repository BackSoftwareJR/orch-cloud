"""Optional API token enforcement for external integrations."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from server.auth import verify_token
from server.config import get_require_api_token


def optional_verify_token(
    authorization: Annotated[str | None, Header()] = None,
    x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None,
) -> None:
    """Require Bearer token when REQUIRE_API_TOKEN=true (production / backcloud)."""
    if not get_require_api_token():
        return
    verify_token(authorization=authorization, x_api_token=x_api_token)


def require_api_token_dep() -> Annotated[None, Depends(optional_verify_token)]:
    return Depends(optional_verify_token)
