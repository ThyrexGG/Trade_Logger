"""Alembic environment for TradeLogger.

The database URL is **not** stored in ``alembic.ini``. It is read from the same
place the application reads it — ``database.get_db_url()`` (which resolves the
``DATABASE_URL`` env var / ``.env``). This keeps one source of truth and keeps
the Supabase URI out of version control.

Migrations are **Postgres-only**. The local SQLite fallback and the pytest path
have no ``DATABASE_URL``; running Alembic there is a no-op error by design — the
at-boot ``database.init_db()`` still builds the SQLite schema for local dev.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the project root importable (env.py runs with CWD = project root, but be
# explicit so `alembic` invoked from elsewhere still works).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None  # raw-SQL migrations; no ORM models to autogenerate from


def _database_url() -> str:
    """Resolve the Postgres URL from the app's own config, or fail loudly."""
    # An explicit override wins (useful for CI against a throwaway PG).
    url = os.getenv("ALEMBIC_DATABASE_URL")
    if not url:
        try:
            from database import get_db_url  # local import: needs sys.path above
        except Exception as exc:  # pragma: no cover - import guard
            raise SystemExit(f"alembic: cannot import database.get_db_url ({exc})")
        url = get_db_url()
    if not url:
        raise SystemExit(
            "alembic: no DATABASE_URL configured. Migrations are Postgres-only; "
            "the local SQLite path is built by database.init_db() at boot."
        )
    # SQLAlchemy 2.x accepts the bare postgres:// scheme only as postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {}) or {}
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
