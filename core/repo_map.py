"""Lightweight repository map for targeted agent context."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.analyzers.detector import detect_framework
from core.models import AgentPreset

SCHEMA_VERSION = "1.0"

_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".hyper-orchestrator",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    ".turbo",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    ".venv",
    "venv",
}

_KEY_ROOT_FILES = (
    "package.json",
    "composer.json",
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
    "artisan",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "tsconfig.json",
    "vite.config.ts",
    "docker-compose.yml",
    "Dockerfile",
    "README.md",
)

_PRESET_FOCUS_DIRS: dict[str, tuple[str, ...]] = {
    AgentPreset.BACKEND.value: (
        "app/Models",
        "app/Http/Controllers",
        "app/Http/Middleware",
        "routes",
        "database/migrations",
        "database/seeders",
        "api",
        "server",
        "src",
    ),
    AgentPreset.UX.value: (
        "components",
        "pages",
        "app",
        "src/components",
        "src/pages",
        "src/app",
        "styles",
        "public",
        "assets",
    ),
    AgentPreset.BUGFIX.value: (
        "app",
        "routes",
        "src",
        "tests",
        "test",
        "spec",
    ),
    AgentPreset.GENERAL.value: (
        "app",
        "routes",
        "src",
        "components",
        "pages",
        "database",
        "api",
    ),
}

_MODULE_DIR_HINTS: tuple[tuple[str, str], ...] = (
    ("app/Models", "models"),
    ("app/Http/Controllers", "controllers"),
    ("routes", "routes"),
    ("database/migrations", "migrations"),
    ("components", "components"),
    ("pages", "pages"),
    ("app", "app"),
    ("src", "src"),
    ("api", "api"),
    ("tests", "tests"),
    ("test", "tests"),
)

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def clear_repo_map_cache() -> None:
    """Clear in-memory repo map cache (primarily for tests)."""
    _cache.clear()


def _fingerprint(project_root: Path) -> float:
    """Return a cache invalidation fingerprint from root and marker file mtimes."""
    mtimes = [project_root.stat().st_mtime]
    for name in _KEY_ROOT_FILES:
        path = project_root / name
        if path.is_file():
            mtimes.append(path.stat().st_mtime)
    return max(mtimes)


def _detect_stack(project_root: Path) -> dict[str, Any]:
    detection = detect_framework(project_root)
    stack: dict[str, Any] = {
        "primary": detection.framework,
        "confidence": round(detection.confidence, 2),
    }

    package_json = project_root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
            if "next" in deps:
                stack["framework"] = "next"
            if "react" in deps:
                stack["ui"] = "react"
            if "typescript" in deps or (project_root / "tsconfig.json").is_file():
                stack["language"] = "typescript"
            elif "javascript" not in stack.get("language", ""):
                stack.setdefault("language", "javascript")
        except (OSError, json.JSONDecodeError):
            pass

    composer_json = project_root / "composer.json"
    if composer_json.is_file():
        stack.setdefault("language", "php")
        try:
            data = json.loads(composer_json.read_text(encoding="utf-8"))
            require = data.get("require") or {}
            if "laravel/framework" in require:
                stack["framework"] = "laravel"
        except (OSError, json.JSONDecodeError):
            pass

    if (project_root / "pyproject.toml").is_file():
        stack.setdefault("language", "python")
    if (project_root / "go.mod").is_file():
        stack.setdefault("language", "go")

    return stack


def _iter_repo_files(project_root: Path, max_files: int) -> tuple[list[str], bool]:
    files: list[str] = []
    truncated = False

    def walk(base: Path) -> None:
        nonlocal truncated
        if truncated:
            return
        try:
            entries = sorted(base.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return
        for entry in entries:
            if truncated:
                return
            if entry.is_dir():
                if entry.name in _SKIP_DIR_NAMES:
                    continue
                walk(entry)
            elif entry.is_file():
                rel = str(entry.relative_to(project_root))
                files.append(rel)
                if len(files) >= max_files:
                    truncated = True
                    return

    walk(project_root)
    return files, truncated


def _top_level_dirs(project_root: Path) -> list[str]:
    dirs: list[str] = []
    try:
        for entry in sorted(project_root.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir() and entry.name not in _SKIP_DIR_NAMES and not entry.name.startswith("."):
                dirs.append(entry.name)
    except OSError:
        return []
    return dirs[:30]


def _key_files(project_root: Path) -> list[str]:
    found: list[str] = []
    for name in _KEY_ROOT_FILES:
        if (project_root / name).is_file():
            found.append(name)
    return found


def _module_index(project_root: Path, rel_dir: str, *, sample_limit: int = 8) -> dict[str, Any] | None:
    path = project_root / rel_dir
    if not path.is_dir():
        return None
    try:
        files = sorted(
            (
                p.relative_to(project_root).as_posix()
                for p in path.rglob("*")
                if p.is_file() and p.name not in (".DS_Store",)
            ),
            key=str,
        )
    except OSError:
        return None
    if not files:
        return None
    module_type = rel_dir.split("/")[-1].lower()
    for hint_path, hint_type in _MODULE_DIR_HINTS:
        if rel_dir == hint_path or rel_dir.endswith(hint_path):
            module_type = hint_type
            break
    return {
        "path": rel_dir,
        "type": module_type,
        "count": len(files),
        "index": files[:sample_limit],
    }


def build_repo_map(project_root: Path, *, max_files: int = 200) -> dict[str, Any]:
    """Build a structured JSON summary of repository layout and stack hints."""
    root = project_root.resolve()
    files, truncated = _iter_repo_files(root, max_files)
    modules: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for rel_dir, _ in _MODULE_DIR_HINTS:
        if rel_dir in seen_paths:
            continue
        module = _module_index(root, rel_dir)
        if module:
            modules.append(module)
            seen_paths.add(rel_dir)

    return {
        "schema_version": SCHEMA_VERSION,
        "project_root": str(root),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "stack": _detect_stack(root),
        "top_level_dirs": _top_level_dirs(root),
        "key_files": _key_files(root),
        "modules": modules,
        "file_count": len(files),
        "truncated": truncated,
    }


def get_repo_map(project_root: Path, *, max_files: int = 200, force_refresh: bool = False) -> dict[str, Any]:
    """Return cached repo map, rebuilding when the project fingerprint changes."""
    root = project_root.resolve()
    key = str(root)
    fingerprint = _fingerprint(root)
    cached = _cache.get(key)
    if not force_refresh and cached is not None and cached[0] == fingerprint:
        return cached[1]
    repo_map = build_repo_map(root, max_files=max_files)
    _cache[key] = (fingerprint, repo_map)
    return repo_map


def _normalize_preset(preset: AgentPreset | str | None) -> str:
    if preset is None:
        return AgentPreset.GENERAL.value
    if isinstance(preset, AgentPreset):
        return preset.value
    return AgentPreset.from_value(preset).value


def format_repo_map_summary(
    repo_map: dict[str, Any],
    *,
    preset: AgentPreset | str | None = None,
    max_chars: int = 1800,
) -> str:
    """Render a compact repo map excerpt for agent prompts."""
    preset_id = _normalize_preset(preset)
    focus_dirs = _PRESET_FOCUS_DIRS.get(preset_id, _PRESET_FOCUS_DIRS[AgentPreset.GENERAL.value])

    stack = repo_map.get("stack") or {}
    stack_bits = [
        str(stack.get("primary", "unknown")),
    ]
    if stack.get("language"):
        stack_bits.append(str(stack["language"]))
    if stack.get("framework"):
        stack_bits.append(str(stack["framework"]))

    lines = [
        f"Stack: {', '.join(stack_bits)} (confidence {stack.get('confidence', 0):.0%})",
        f"Top-level: {', '.join(repo_map.get('top_level_dirs') or []) or '(none)'}",
    ]
    key_files = repo_map.get("key_files") or []
    if key_files:
        lines.append(f"Key files: {', '.join(key_files[:12])}")

    modules: list[dict[str, Any]] = list(repo_map.get("modules") or [])
    focus_modules = [m for m in modules if m.get("path") in focus_dirs]
    other_modules = [m for m in modules if m.get("path") not in focus_dirs]
    ordered_modules = focus_modules + other_modules

    if ordered_modules:
        lines.append("Notable dirs:")
        for module in ordered_modules:
            path = module.get("path", "?")
            count = module.get("count", 0)
            index = module.get("index") or []
            sample = ", ".join(index[:4])
            marker = "*" if path in focus_dirs else "-"
            line = f"{marker} {path} ({count} files"
            if sample:
                line += f": {sample}"
            line += ")"
            lines.append(line)

    if repo_map.get("truncated"):
        lines.append(f"(file scan capped at {repo_map.get('file_count', '?')} entries)")

    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20].rstrip() + "\n…[truncated]"
