import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def db_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A freshly seeded database, built once per test session."""
    path = tmp_path_factory.mktemp("db") / "caredesk.db"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_db.py"), "--output", str(path)],
        check=True,
        capture_output=True,
    )
    return path


@pytest.fixture
def db_env(db_file: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the app at the seeded test database."""
    monkeypatch.setenv("CAREDESK_DB_PATH", str(db_file))
    return db_file
