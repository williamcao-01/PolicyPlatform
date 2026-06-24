from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DatabaseSettings, get_settings


def build_engine(settings: DatabaseSettings | None = None):
    database = settings or get_settings().database
    return create_engine(
        database.url,
        echo=database.echo,
        pool_size=database.pool_size,
        max_overflow=database.max_overflow,
        pool_pre_ping=database.pool_pre_ping,
    )


def build_session_factory(settings: DatabaseSettings | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=build_engine(settings), autoflush=False, expire_on_commit=False)


SessionLocal = build_session_factory()


@contextmanager
def session_scope(session_factory: sessionmaker[Session] = SessionLocal) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
