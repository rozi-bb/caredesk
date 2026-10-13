import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from agent.db import DEFAULT_DATABASE_URL, url_with_database

ROOT = Path(__file__).resolve().parents[1]
TEST_PASSWORD = "test-password-123"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


def seed(url: str, accounts_file: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "seed_db.py"),
            "--database-url",
            url,
            "--demo-password",
            TEST_PASSWORD,
            "--accounts-file",
            str(accounts_file),
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session")
def make_database(tmp_path_factory: pytest.TempPathFactory) -> Iterator[object]:
    """Create seeded throwaway databases on the local server; drop them afterwards.

    Tests never touch the caredesk database itself.
    """
    server = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    created: list[str] = []

    def create() -> str:
        name = f"caredesk_test_{uuid.uuid4().hex[:10]}"
        with psycopg.connect(server, autocommit=True) as conn:
            conn.execute(f'CREATE DATABASE "{name}"')
        created.append(name)
        url = url_with_database(server, name)
        seed(url, tmp_path_factory.mktemp("accounts") / "accounts.csv")
        return url

    yield create
    with psycopg.connect(server, autocommit=True) as conn:
        for name in created:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture(scope="session")
def test_password() -> str:
    """The password every account in the test databases has."""
    return TEST_PASSWORD


@pytest.fixture(scope="session")
def db_url(make_database) -> str:
    """One seeded database shared by the whole test session."""
    return make_database()


@pytest.fixture
def db_env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Point the app at the seeded test database."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    return db_url
