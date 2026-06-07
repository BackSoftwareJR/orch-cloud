"""Map n8n / CRM specialist role labels to orchestrator presets."""

from __future__ import annotations

_ROLE_PRESET_MAP: dict[str, str] = {
    "frontend": "ux",
    "frontend dev": "ux",
    "frontend developer": "ux",
    "front-end": "ux",
    "front end": "ux",
    "ui": "ux",
    "ux": "ux",
    "design": "ux",
    "backend": "backend",
    "backend dev": "backend",
    "backend developer": "backend",
    "back-end": "backend",
    "api": "backend",
    "bugfix": "bugfix",
    "bug fix": "bugfix",
    "bug fixer": "bugfix",
    "debugger": "bugfix",
    "general": "general",
    "full stack": "general",
    "fullstack": "general",
    "architect": "general",
}


def resolve_preset_from_specialist_role(role: str | None) -> str:
    """Return orchestrator preset id for a CRM specialist role string."""
    if not role or not role.strip():
        return "general"
    normalized = " ".join(role.strip().lower().split())
    if normalized in _ROLE_PRESET_MAP:
        return _ROLE_PRESET_MAP[normalized]
    for key, preset in _ROLE_PRESET_MAP.items():
        if key in normalized or normalized in key:
            return preset
    return "general"
