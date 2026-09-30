"""Tests for /health, /health/db and /api/v1/hello."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import get_db
from app.main import app


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "KaushalSetu API"
    # The API started with the validated config/scoring.yaml.
    assert body["scoring_config_version"].startswith("v")
    assert len(body["scoring_config_sha256"]) == 64


def test_hello_returns_message(client):
    response = client.get("/api/v1/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from the KaushalSetu API"}


def test_root_redirects_to_docs(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/docs"


def test_health_db_returns_503_when_database_is_unreachable(client):
    # Point the endpoint at a port where nothing listens, so the connection fails fast.
    broken_engine = create_engine(
        "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none",
        connect_args={"connect_timeout": 1},
    )
    BrokenSession = sessionmaker(bind=broken_engine)

    def broken_db():
        session = BrokenSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = broken_db
    try:
        response = client.get("/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["database"] == "unreachable"


@pytest.mark.db
def test_health_db_returns_ok_with_pgvector(client, require_db):
    response = client.get("/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert (
        body["pgvector"]["installed"] is True
    ), "pgvector extension is not enabled. Run: alembic upgrade head"
