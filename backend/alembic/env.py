"""Alembic migration environment.

The database URL comes from the application settings (the repository .env file), so there
is exactly one place to configure the database. Tests can point Alembic at another
database by setting ``config.attributes["database_url"]`` before running a command.
"""

from logging.config import fileConfig

from alembic import context
from pgvector.sqlalchemy import Vector
from sqlalchemy import create_engine, pool

from app.core.settings import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    # Keep loggers created by the app/pytest working when migrations run inside tests.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
database_url = config.attributes.get("database_url") or get_settings().sqlalchemy_url


def render_item(type_, obj, autogen_context):
    """Write pgvector columns as `Vector(384)` in generated migration files."""
    if type_ == "type" and isinstance(obj, Vector):
        autogen_context.imports.add("from pgvector.sqlalchemy import Vector")
        return f"Vector({obj.dim})"
    return False  # use Alembic's default rendering for everything else


def run_migrations_offline() -> None:
    """Generate SQL without connecting ('alembic upgrade head --sql')."""
    url = (
        database_url
        if isinstance(database_url, str)
        else database_url.render_as_string(hide_password=False)
    )
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and apply migrations."""
    connectable = create_engine(
        database_url,
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": get_settings().db_connect_timeout_seconds},
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
