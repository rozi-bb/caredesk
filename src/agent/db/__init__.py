"""Connections to the home's Postgres database (ADR-0021)."""

import os
from datetime import date
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg.rows import dict_row

# "Today" inside the synthetic data. Fixed so that answers about "today"
# do not change from one day to the next and evaluations stay comparable.
REFERENCE_DATE = date(2026, 10, 5)

DEFAULT_DATABASE_URL = "postgresql://caredesk:caredesk@localhost:5432/caredesk"

Connection = psycopg.Connection[dict[str, Any]]


def database_url() -> str:
    """Return the database URL, from DATABASE_URL or the local Docker default."""
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def url_with_database(url: str, name: str) -> str:
    """Return the same server's URL, pointing at another database on it."""
    return urlunsplit(urlsplit(url)._replace(path=f"/{name}"))


def connect_readonly() -> Connection:
    """Open a connection whose transactions are read-only.

    Postgres rejects any write on it, so tools cannot change data even by
    mistake. Raises psycopg.OperationalError if the database is unreachable.
    """
    conn = psycopg.connect(database_url(), row_factory=dict_row)
    conn.read_only = True
    return conn
