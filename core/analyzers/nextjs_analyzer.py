"""Next.js project analyzer."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from core.analyzers.base_analyzer import BaseAnalyzer
from core.models import AnalysisResult

logger = logging.getLogger(__name__)


class NextJsAnalyzer(BaseAnalyzer):
    """Parses package.json, router structure, middleware, and test setup."""

    framework = "nextjs"

    @classmethod
    def can_analyze(cls, project_root: Path) -> bool:
        package_json = project_root / "package.json"
        if not package_json.is_file():
            return False
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        deps = data.get("dependencies", {})
        dev_deps = data.get("devDependencies", {})
        if not isinstance(deps, dict):
            deps = {}
        if not isinstance(dev_deps, dict):
            dev_deps = {}
        return "next" in deps or "next" in dev_deps

    def analyze(self) -> AnalysisResult:
        package = self._parse_package_json()
        router_type, routes = self._map_router_structure()
        scripts = package.get("scripts", {})
        if not isinstance(scripts, dict):
            scripts = {}

        middleware = self._detect_middleware()
        api_routes = self._detect_api_routes(routes)
        ts_paths = self._parse_tsconfig_paths()
        test_info = self._detect_test_setup(scripts, package)

        next_version = self._next_version(package)
        summary_lines = [
            f"- Next.js version: `{next_version}`",
            f"- Router type: `{router_type}`",
            f"- Route entries mapped: {len(routes)}",
            f"- Middleware: `{middleware or 'none'}`",
            f"- Test runner: `{test_info['runner']}`",
        ]

        details: dict[str, object] = {
            "package": package,
            "router_type": router_type,
            "routes": routes,
            "middleware": middleware,
            "api_routes": api_routes,
            "tsconfig_paths": ts_paths,
            "test_info": test_info,
            "test_command": test_info["command"],
        }

        markdown = "\n".join(
            [
                self.format_markdown_section("Next.js Overview", "\n".join(summary_lines)),
                self.format_markdown_section("Scripts", self._format_scripts(scripts)),
                self.format_markdown_section(
                    "Router Structure",
                    self._format_routes(router_type, routes) or "_No routes mapped._",
                ),
                self.format_markdown_section(
                    "Middleware",
                    f"- File: `{middleware}`" if middleware else "_No middleware.ts/js found._",
                ),
                self.format_markdown_section(
                    "API Routes",
                    self._format_api_routes(api_routes) or "_No API routes detected._",
                ),
                self.format_markdown_section(
                    "TypeScript Paths",
                    self._format_ts_paths(ts_paths) or "_No path aliases configured._",
                ),
                self.format_markdown_section(
                    "Testing",
                    self._format_testing(test_info),
                ),
            ]
        )

        return AnalysisResult(
            framework=self.framework,
            summary=markdown,
            details=details,
            confidence=1.0,
        )

    def _parse_package_json(self) -> dict[str, object]:
        raw = self._read_text("package.json")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as exc:
            logger.warning("Invalid package.json: %s", exc)
        return {}

    def _next_version(self, package: dict[str, object]) -> str:
        for section in ("dependencies", "devDependencies"):
            deps = package.get(section, {})
            if isinstance(deps, dict) and "next" in deps:
                return str(deps["next"])
        return "unknown"

    def _map_router_structure(self) -> tuple[str, list[dict[str, str]]]:
        app_dir = self.project_root / "app"
        pages_dir = self.project_root / "pages"
        src_app = self.project_root / "src" / "app"
        src_pages = self.project_root / "src" / "pages"

        if app_dir.is_dir() or src_app.is_dir():
            base = src_app if src_app.is_dir() else app_dir
            return "app", self._scan_app_router(base)

        if pages_dir.is_dir() or src_pages.is_dir():
            base = src_pages if src_pages.is_dir() else pages_dir
            return "pages", self._scan_pages_router(base)

        return "unknown", []

    def _scan_app_router(self, base: Path) -> list[dict[str, str]]:
        routes: list[dict[str, str]] = []
        for page in sorted(base.rglob("page.*")):
            if page.suffix not in {".tsx", ".ts", ".jsx", ".js"}:
                continue
            rel = page.relative_to(base)
            route_path = self._app_route_from_segments(rel.parts[:-1])
            routes.append(
                {"type": "page", "path": route_path, "file": str(page.relative_to(self.project_root))}
            )
        for layout in sorted(base.rglob("layout.*")):
            if layout.suffix not in {".tsx", ".ts", ".jsx", ".js"}:
                continue
            rel = layout.relative_to(base)
            route_path = self._app_route_from_segments(rel.parts[:-1])
            routes.append(
                {"type": "layout", "path": route_path, "file": str(layout.relative_to(self.project_root))}
            )
        return routes

    def _scan_pages_router(self, base: Path) -> list[dict[str, str]]:
        routes: list[dict[str, str]] = []
        for page in sorted(base.rglob("*")):
            if not page.is_file():
                continue
            if page.suffix not in {".tsx", ".ts", ".jsx", ".js"}:
                continue
            if page.name.startswith("_"):
                continue
            rel = page.relative_to(base)
            route_path = self._pages_route_from_file(rel)
            routes.append(
                {"type": "page", "path": route_path, "file": str(page.relative_to(self.project_root))}
            )
        return routes

    def _detect_middleware(self) -> str | None:
        for candidate in (
            "middleware.ts",
            "middleware.js",
            "src/middleware.ts",
            "src/middleware.js",
        ):
            path = self.project_root / candidate
            if path.is_file():
                return candidate
        return None

    def _detect_api_routes(self, routes: list[dict[str, str]]) -> list[str]:
        api_paths: list[str] = []
        for route in routes:
            path = route.get("path", "")
            if "/api" in path or path.startswith("/api"):
                api_paths.append(f"{path} → `{route['file']}`")
        api_dir = self.project_root / "pages" / "api"
        src_api = self.project_root / "src" / "pages" / "api"
        for base in (api_dir, src_api):
            if base.is_dir():
                for f in sorted(base.rglob("*")):
                    if f.is_file() and f.suffix in {".ts", ".tsx", ".js", ".jsx"}:
                        rel = str(f.relative_to(self.project_root))
                        if rel not in api_paths:
                            api_paths.append(rel)
        return api_paths[:30]

    def _parse_tsconfig_paths(self) -> dict[str, list[str]]:
        for candidate in ("tsconfig.json", "tsconfig.base.json"):
            raw = self._read_text(candidate)
            if not raw:
                continue
            try:
                data = json.loads(raw)
                compiler = data.get("compilerOptions", {})
                if isinstance(compiler, dict):
                    paths = compiler.get("paths", {})
                    if isinstance(paths, dict):
                        return {k: v if isinstance(v, list) else [str(v)] for k, v in paths.items()}
            except json.JSONDecodeError:
                continue
        return {}

    def _detect_test_setup(
        self, scripts: dict[str, object], package: dict[str, object]
    ) -> dict[str, str]:
        dev_deps = package.get("devDependencies", {})
        deps = package.get("dependencies", {})
        if not isinstance(dev_deps, dict):
            dev_deps = {}
        if not isinstance(deps, dict):
            deps = {}
        all_deps = {**deps, **dev_deps}

        config_files = []
        for name in (
            "jest.config.js",
            "jest.config.ts",
            "vitest.config.ts",
            "vitest.config.mts",
            "playwright.config.ts",
        ):
            if (self.project_root / name).is_file():
                config_files.append(name)

        runner = "unknown"
        command = "npm run test"

        if "vitest" in all_deps:
            runner = "Vitest"
            command = "npm run test" if "test" in scripts else "npx vitest run"
        elif "jest" in all_deps or "@jest/core" in all_deps:
            runner = "Jest"
            command = "npm run test" if "test" in scripts else "npx jest"
        elif "@playwright/test" in all_deps:
            runner = "Playwright"
            command = "npx playwright test"
        elif "test" in scripts:
            runner = "npm script"
            command = "npm run test"
        elif "test:unit" in scripts:
            runner = "npm script"
            command = "npm run test:unit"
        elif "test:ci" in scripts:
            runner = "npm script"
            command = "npm run test:ci"

        return {"runner": runner, "command": command, "config_files": ", ".join(config_files) or "none"}

    @staticmethod
    def _app_route_from_segments(segments: tuple[str, ...]) -> str:
        if not segments:
            return "/"
        parts: list[str] = []
        for segment in segments:
            if segment.startswith("(") and segment.endswith(")"):
                continue
            parts.append(segment)
        return "/" + "/".join(parts) if parts else "/"

    @staticmethod
    def _pages_route_from_file(rel: Path) -> str:
        parts = list(rel.parts)
        stem = rel.stem
        if stem == "index":
            parts = parts[:-1]
        else:
            parts[-1] = stem
        if not parts:
            return "/"
        return "/" + "/".join(parts)

    @staticmethod
    def _format_scripts(scripts: dict[str, object]) -> str:
        if not scripts:
            return "_No npm scripts defined._"
        lines = [f"- `{name}`: `{value}`" for name, value in sorted(scripts.items())]
        return "\n".join(lines)

    @staticmethod
    def _format_routes(router_type: str, routes: list[dict[str, str]]) -> str:
        if not routes:
            return ""
        lines = [f"Router: **{router_type}**", ""]
        for route in routes[:50]:
            lines.append(f"- `{route['path']}` ({route['type']}) → `{route['file']}`")
        if len(routes) > 50:
            lines.append(f"\n_...and {len(routes) - 50} more routes._")
        return "\n".join(lines)

    @staticmethod
    def _format_api_routes(api_routes: list[str]) -> str:
        if not api_routes:
            return ""
        return "\n".join(f"- {r}" for r in api_routes)

    @staticmethod
    def _format_ts_paths(paths: dict[str, list[str]]) -> str:
        if not paths:
            return ""
        lines = []
        for alias, targets in sorted(paths.items()):
            lines.append(f"- `{alias}` → {', '.join(f'`{t}`' for t in targets)}")
        return "\n".join(lines)

    @staticmethod
    def _format_testing(test_info: dict[str, str]) -> str:
        return (
            f"- Runner: `{test_info['runner']}`\n"
            f"- Recommended command: `{test_info['command']}`\n"
            f"- Config: `{test_info.get('config_files', 'none')}`"
        )
