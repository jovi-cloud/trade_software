"""Alembic environment.

The database URL comes from application settings, so migrations always target
the same database the app uses.
"""

from __future__ import annotations

from logging.config import fileConfig

# Importing app.models registers every ORM model on Base.metadata so that
# --autogenerate can see them. Models arrive in Phase 1.
import app.models  # noqa: F401
from alembic import context
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import create_db_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return get_settings().sqlalchemy_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a DBAPI connection."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite cannot ALTER most things in place; batch mode rebuilds the
        # table instead. Required for nearly every non-trivial migration.
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = create_db_engine(get_settings())

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
