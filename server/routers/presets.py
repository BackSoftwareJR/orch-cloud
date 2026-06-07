"""Agent preset discovery endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.presets.registry import PRESET_SCHEMA_VERSION, get_preset, list_presets
from server.schemas import PresetDetailResponse, PresetResponse

router = APIRouter(prefix="/presets", tags=["presets"])


def _to_response(preset) -> PresetResponse:
    return PresetResponse(
        id=preset.id.value,
        label=preset.label,
        description=preset.description,
        default_level=preset.default_level.name.lower(),
        capabilities=list(preset.allowed_file_patterns) or ["general-purpose"],
        version=preset.version or PRESET_SCHEMA_VERSION,
    )


@router.get("", response_model=list[PresetResponse])
def list_available_presets() -> list[PresetResponse]:
    return [_to_response(preset) for preset in list_presets()]


@router.get("/{preset_id}", response_model=PresetDetailResponse)
def get_preset_detail(preset_id: str) -> PresetDetailResponse:
    try:
        preset = get_preset(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    base = _to_response(preset)
    return PresetDetailResponse(
        **base.model_dump(),
        example_payload={
            "task": "Describe your change here",
            "preset": preset.id.value,
            "level": preset.default_level.name.lower(),
        },
        forbidden_actions=list(preset.forbidden_actions),
        quality_checklist=list(preset.quality_checklist),
        output_expectations=preset.output_expectations,
    )
