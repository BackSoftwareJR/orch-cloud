"""Cursor agent model discovery endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from core.presets.registry import MODEL_REGISTRY
from server.schemas import ModelResponse

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelResponse])
def list_models() -> list[ModelResponse]:
    return [
        ModelResponse(
            slug=info.slug,
            label=info.label,
            tier=info.tier,
            description=info.description,
        )
        for info in MODEL_REGISTRY.values()
    ]
