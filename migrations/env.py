"""Alembic environment: run migrations against DATABASE_URL.

Migrations are plain SQL (op.execute); there are no ORM models.
"""

from alembic import context
from sqlalchemy import create_engine

from agent.db import database_url


def _sqlalchemy_url() -> str:
    # SQLAlchemy needs the driver named in the URL; the app itself uses psycopg directly.
    url = context.config.attributes.get("database_url") or database_url()
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_online() -> None:
    """Apply migrations over a live connection."""
    engine = create_engine(_sqlalchemy_url())
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
