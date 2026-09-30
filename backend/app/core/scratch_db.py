"""The scratch database "<your db>_test": created on demand and migrated to the latest version.

Used by pytest and by evaluation tools, which work inside a transaction that is rolled back,
so the development database is never touched.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from app.core.settings import Settings, get_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config(database_url: URL) -> Config:
    """Alembic configuration pointing at `database_url` instead of the .env database."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["database_url"] = database_url
    return config


def scratch_database_url(settings: Settings | None = None) -> URL:
    main_url = make_url((settings or get_settings()).sqlalchemy_url)
    return main_url.set(database=f"{main_url.database}_test")


def prepare_scratch_database(settings: Settings | None = None) -> URL:
    """Create the scratch database if needed and migrate it to the latest version."""
    settings = settings or get_settings()
    main_url = make_url(settings.sqlalchemy_url)
    url = scratch_database_url(settings)
    # CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT.
    admin = create_engine(main_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        ).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()
    command.upgrade(alembic_config(url), "head")
    return url
