"""Project lookup and auto-creation for webhook / n8n integrations."""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy.orm import Session

from core.security import validate_repo_url
from server.models import Project


def repo_name_from_url(repo_url: str) -> str:
    path = urlparse(repo_url).path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    name = path.rsplit("/", 1)[-1] if path else "project"
    return name or "project"


def normalize_repo_url(repo_url: str) -> str:
    """Canonical form for matching (lowercase, no .git suffix, no trailing slash)."""
    url = repo_url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url.lower()


def find_project_by_github_url(db: Session, github_url: str) -> Project | None:
    target = normalize_repo_url(github_url)
    for project in db.query(Project).all():
        if normalize_repo_url(project.repo_url) == target:
            return project
        settings = project.settings or {}
        stored = settings.get("github_url") or settings.get("repo_url")
        if stored and normalize_repo_url(str(stored)) == target:
            return project
    return None


def get_or_create_project_from_github(
    db: Session,
    *,
    github_url: str,
    website_url: str | None = None,
    crm_project_id: str | None = None,
    crm_log_url: str | None = None,
) -> Project:
    repo_url = validate_repo_url(github_url)
    existing = find_project_by_github_url(db, repo_url)
    if existing is not None:
        settings = dict(existing.settings or {})
        changed = False
        if website_url and settings.get("website_url") != website_url:
            settings["website_url"] = website_url
            changed = True
        if crm_project_id and settings.get("crm_project_id") != crm_project_id:
            settings["crm_project_id"] = crm_project_id
            changed = True
        if crm_log_url and settings.get("crm_log_url") != crm_log_url:
            settings["crm_log_url"] = crm_log_url
            changed = True
        if settings.get("github_url") != repo_url:
            settings["github_url"] = repo_url
            changed = True
        if changed:
            existing.settings = settings
            db.flush()
        return existing

    settings: dict[str, str] = {"github_url": repo_url}
    if website_url:
        settings["website_url"] = website_url
    if crm_project_id:
        settings["crm_project_id"] = crm_project_id
    if crm_log_url:
        settings["crm_log_url"] = crm_log_url

    project = Project(
        name=repo_name_from_url(repo_url),
        repo_url=repo_url,
        settings=settings,
    )
    db.add(project)
    db.flush()
    return project
