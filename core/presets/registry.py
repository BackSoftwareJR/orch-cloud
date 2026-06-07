"""Registry of specialized agent presets for HyperOrchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from core.models import AgentPreset, TaskLevel

TestStrategy = Literal["skip", "run", "run_lint", "run_build", "run_focused"]
PRESET_SCHEMA_VERSION = "2.0"
DEFAULT_AGENT_MODEL = "composer-2.5"

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class PresetDefinition:
    id: AgentPreset
    label: str
    description: str
    default_level: TaskLevel
    system_prompt: str
    output_expectations: str
    quality_checklist: tuple[str, ...] = ()
    context_priorities: dict[str, int] = field(default_factory=dict)
    strict_by_default: bool = False
    test_strategy: TestStrategy = "run"
    push_on_test_failure: bool = False
    model: str = DEFAULT_AGENT_MODEL
    yolo: bool = True
    version: str = PRESET_SCHEMA_VERSION
    pro_decompose_prompt: str | None = None
    allowed_file_patterns: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()

    @property
    def constraints_block(self) -> str:
        lines: list[str] = ["## Preset constraints"]
        if self.allowed_file_patterns:
            lines.append(
                "Prefer editing files matching: "
                + ", ".join(f"`{pattern}`" for pattern in self.allowed_file_patterns)
            )
        for action in self.forbidden_actions:
            lines.append(f"- DO NOT: {action}")
        return "\n".join(lines)

    @property
    def quality_block(self) -> str:
        lines = ["## Quality checklist (verify before finishing)"]
        for item in self.quality_checklist:
            lines.append(f"- [ ] {item}")
        lines.extend(["", "## Expected output", self.output_expectations])
        return "\n".join(lines)


def _load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Preset prompt missing: {path}")
    return path.read_text(encoding="utf-8").strip()


_UX_PRIORITIES = {
    "routes": 0,
    "router structure": 0,
    "dependencies": 1,
    "scripts": 2,
    "typescript paths": 2,
    "models": 8,
    "migrations": 9,
    "api routes": 9,
}

_BACKEND_PRIORITIES = {
    "models": 0,
    "migrations": 0,
    "controllers": 1,
    "api routes": 1,
    "middleware": 2,
    "routes": 3,
    "testing": 4,
}

_BUGFIX_PRIORITIES = {
    "testing": 0,
    "routes": 1,
    "api routes": 1,
    "models": 2,
    "controllers": 2,
    "dependencies": 3,
}

_UX_CHECKLIST = (
    "Visual hierarchy is clear on mobile and desktop",
    "Spacing follows a consistent 4/8px grid",
    "Color contrast meets WCAG AA for body text",
    "Focus states and keyboard navigation work",
    "Layout matches existing brand/style tokens",
    "No unrelated backend files were modified",
)

_BACKEND_CHECKLIST = (
    "Input validated at API boundaries",
    "Auth/authz applied on protected routes",
    "Database changes include safe migrations",
    "No N+1 queries on list endpoints touched",
    "Errors return structured responses without stack traces",
    "Existing API contracts preserved unless task requires break",
)

_BUGFIX_CHECKLIST = (
    "Root cause identified and fixed (not just symptoms)",
    "Diff is minimal — no unrelated refactors",
    "Fix verified against the reported failure path",
    "No new features added beyond the bug scope",
    "Tests updated or added if harness exists",
)

_GENERAL_CHECKLIST = (
    "Changes match existing project conventions",
    "Only task-relevant files modified",
    "No debug code or TODO placeholders left",
    "Repository is commit-ready",
)


def _build_registry() -> dict[AgentPreset, PresetDefinition]:
    return {
        AgentPreset.GENERAL: PresetDefinition(
            id=AgentPreset.GENERAL,
            label="General",
            description="Balanced architect for any full-stack task.",
            default_level=TaskLevel.MEDIUM,
            system_prompt=_load_prompt("general"),
            output_expectations="Production-ready code aligned with project conventions.",
            quality_checklist=_GENERAL_CHECKLIST,
            test_strategy="run",
            yolo=True,
            pro_decompose_prompt=(
                "You are a senior software architect. Break the task into atomic sequential "
                "steps for an AI coding agent. Return ONLY valid JSON."
            ),
        ),
        AgentPreset.UX: PresetDefinition(
            id=AgentPreset.UX,
            label="UX / UI Design",
            description="Principal designer for cohesive, accessible, editorial-grade interfaces.",
            default_level=TaskLevel.MEDIUM,
            system_prompt=_load_prompt("ux"),
            output_expectations=(
                "Polished UI with responsive layout, design-system consistency, and WCAG AA accessibility."
            ),
            quality_checklist=_UX_CHECKLIST,
            context_priorities=_UX_PRIORITIES,
            test_strategy="run_lint",
            push_on_test_failure=True,
            yolo=True,
            allowed_file_patterns=(
                "*.html",
                "*.css",
                "*.scss",
                "*.sass",
                "*.less",
                "components/**",
                "pages/**",
                "app/**",
                "public/**",
                "assets/**",
                "styles/**",
            ),
            forbidden_actions=(
                "modify database migrations or schema",
                "change API route handlers unless required for UI data binding",
                "refactor backend services unrelated to the visual task",
            ),
            pro_decompose_prompt=(
                "You are a UX architect. Decompose into: layout structure, component styling, "
                "responsive breakpoints, accessibility, micro-interactions. Return ONLY valid JSON."
            ),
        ),
        AgentPreset.BACKEND: PresetDefinition(
            id=AgentPreset.BACKEND,
            label="Backend",
            description="Principal backend engineer for APIs, data layer, and server logic.",
            default_level=TaskLevel.MEDIUM,
            system_prompt=_load_prompt("backend"),
            output_expectations=(
                "Secure, observable backend changes with validated inputs and safe migrations."
            ),
            quality_checklist=_BACKEND_CHECKLIST,
            context_priorities=_BACKEND_PRIORITIES,
            test_strategy="run",
            yolo=True,
            allowed_file_patterns=(
                "app/**",
                "routes/**",
                "database/**",
                "api/**",
                "server/**",
                "src/**",
                "*.php",
                "*.py",
                "*.go",
            ),
            forbidden_actions=(
                "redesign marketing pages or global CSS themes",
                "change front-end layout unless required for API integration",
            ),
            pro_decompose_prompt=(
                "You are a backend architect. Decompose into API, data, validation, and test steps. "
                "Return ONLY valid JSON."
            ),
        ),
        AgentPreset.BUGFIX: PresetDefinition(
            id=AgentPreset.BUGFIX,
            label="Bug Fix",
            description="Staff engineer for root-cause analysis and surgical fixes.",
            default_level=TaskLevel.FAST,
            system_prompt=_load_prompt("bugfix"),
            output_expectations="Minimal diff that fixes root cause with no scope creep.",
            quality_checklist=_BUGFIX_CHECKLIST,
            context_priorities=_BUGFIX_PRIORITIES,
            strict_by_default=True,
            test_strategy="run_focused",
            yolo=False,
            forbidden_actions=(
                "add new features beyond fixing the reported issue",
                "refactor unrelated modules",
                "reformat files you did not need to change",
            ),
            pro_decompose_prompt=(
                "You are a debugging lead. Decompose into: reproduce, isolate root cause, "
                "minimal fix, verify. Return ONLY valid JSON."
            ),
        ),
    }


@lru_cache(maxsize=1)
def _registry() -> dict[AgentPreset, PresetDefinition]:
    return _build_registry()


def get_preset(preset: AgentPreset | str) -> PresetDefinition:
    if not isinstance(preset, AgentPreset):
        preset = AgentPreset.from_value(preset)
    return _registry()[preset]


def list_presets() -> list[PresetDefinition]:
    return list(_registry().values())


def resolve_level(
    preset: AgentPreset | str,
    level_override: str | int | TaskLevel | None,
) -> TaskLevel:
    """Use explicit level when provided; otherwise preset default."""
    if level_override is not None and str(level_override).strip():
        return TaskLevel.from_value(level_override)
    return get_preset(preset).default_level
