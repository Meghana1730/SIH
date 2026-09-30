"""Shared pytest fixtures.

Database tests use a SEPARATE database named "<your db>_test" (e.g. kaushalsetu_test) inside
the same PostgreSQL container. It is created automatically and migrated to the latest
version, so tests never touch the development database.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.core.db import engine, get_db
from app.core.scratch_db import alembic_config, prepare_scratch_database
from app.main import app
from app.services.auth import auth_limiters

__all__ = ["alembic_config"]  # re-exported for tests that run Alembic commands


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _database_reachable() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
def require_db() -> None:
    """Skip (with a clear reason) when the database container is not running."""
    if not _database_reachable():
        pytest.skip("PostgreSQL not reachable. Start it with: docker compose up -d db")


# ---------------------------------------------------------------- test database
@pytest.fixture(scope="session")
def test_db_url() -> URL:
    """Create the test database if needed and migrate it to the latest version."""
    if not _database_reachable():
        pytest.skip("PostgreSQL not reachable. Start it with: docker compose up -d db")
    return prepare_scratch_database()


@pytest.fixture(scope="session")
def test_engine(test_db_url: URL) -> Iterator[Engine]:
    test_engine = create_engine(test_db_url, connect_args={"connect_timeout": 3})
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    """A session whose changes are ALWAYS rolled back after the test (the test DB stays empty)."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def api(db_session: Session) -> Iterator[TestClient]:
    """An API client whose endpoints use `db_session` (the test database, rolled back after
    the test). Login rate-limit counters start empty for every test."""

    def use_test_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = use_test_session
    auth_limiters().clear_all()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        auth_limiters().clear_all()
