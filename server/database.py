"""SQLAlchemy database engine and session factory."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from server.config import get_database_url

engine = create_engine(
    get_database_url(),
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from server import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_schema()


def _migrate_schema() -> None:
    """Add columns introduced after initial deploys (SQLite-safe)."""
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(jobs)").fetchall()
        existing = {row[1] for row in rows}
        if "parent_job_id" not in existing:
            conn.exec_driver_sql("ALTER TABLE jobs ADD COLUMN parent_job_id VARCHAR(36)")
        if "thread_root_id" not in existing:
            conn.exec_driver_sql("ALTER TABLE jobs ADD COLUMN thread_root_id VARCHAR(36)")
        if "preset" not in existing:
            conn.exec_driver_sql(
                "ALTER TABLE jobs ADD COLUMN preset VARCHAR(32) NOT NULL DEFAULT 'general'"
            )
        if "model" not in existing:
            conn.exec_driver_sql("ALTER TABLE jobs ADD COLUMN model VARCHAR(64)")
