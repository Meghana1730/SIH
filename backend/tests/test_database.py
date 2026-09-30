"""Checks that PostgreSQL and pgvector actually work (not just that they are installed)."""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.db import engine

pytestmark = pytest.mark.db

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_pgvector_computes_distance(require_db):
    with engine.connect() as connection:
        distance = connection.execute(
            text("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector")
        ).scalar_one()
    assert distance == pytest.approx(1.0)


def test_database_is_at_latest_migration(require_db):
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    latest = ScriptDirectory.from_config(config).get_current_head()

    with engine.connect() as connection:
        current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert current == latest, "Database is behind. Run: alembic upgrade head"
