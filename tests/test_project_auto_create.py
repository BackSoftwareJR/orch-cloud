"""Tests for auto project creation from GitHub URLs."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from server.database import Base
from server.models import Project
from server.project_service import (
    find_project_by_github_url,
    get_or_create_project_from_github,
    normalize_repo_url,
    repo_name_from_url,
)


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_normalize_repo_url_strips_git_suffix() -> None:
    assert normalize_repo_url("https://github.com/org/repo.git/") == normalize_repo_url(
        "https://github.com/org/repo"
    )


def test_repo_name_from_url() -> None:
    assert repo_name_from_url("https://github.com/BackSoftwareJR/villa_sole") == "villa_sole"


def test_get_or_create_project_creates_new() -> None:
    db = _session()
    project = get_or_create_project_from_github(
        db,
        github_url="https://github.com/BackSoftwareJR/villa_sole",
        website_url="https://villa-sole.example.com",
        crm_project_id="crm-42",
    )
    db.commit()
    assert project.name == "villa_sole"
    assert project.repo_url == "https://github.com/BackSoftwareJR/villa_sole"
    assert project.settings["website_url"] == "https://villa-sole.example.com"
    assert project.settings["crm_project_id"] == "crm-42"


def test_get_or_create_project_finds_existing_without_git_suffix() -> None:
    db = _session()
    existing = Project(
        name="villa_sole",
        repo_url="https://github.com/BackSoftwareJR/villa_sole.git",
        settings={"github_url": "https://github.com/BackSoftwareJR/villa_sole"},
    )
    db.add(existing)
    db.commit()

    project = get_or_create_project_from_github(
        db,
        github_url="https://github.com/BackSoftwareJR/villa_sole",
    )
    assert project.id == existing.id


def test_find_project_by_github_url_matches_settings_field() -> None:
    db = _session()
    project = Project(
        name="legacy",
        repo_url="https://github.com/org/legacy",
        settings={"github_url": "https://github.com/org/legacy"},
    )
    db.add(project)
    db.commit()

    found = find_project_by_github_url(db, "https://github.com/org/legacy.git")
    assert found is not None
    assert found.id == project.id
