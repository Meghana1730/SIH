"""Database engine and session factory (SQLAlchemy 2, synchronous; see ADR-05)."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings

_settings = get_settings()

# Creating the engine does not connect yet; the first query opens a connection.
engine: Engine = create_engine(
    _settings.sqlalchemy_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": _settings.db_connect_timeout_seconds},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
