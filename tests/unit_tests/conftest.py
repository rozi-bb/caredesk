"""Backend fixtures shared by the API and Telegram tests."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from .fakes import FakeModel, app_with_fakes


@pytest.fixture(autouse=True)
def no_jev_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Unit tests make no API calls: a graph built without a fake Jev must fail
    # over to its fake fallback, never reach TypeSafe.
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)


@pytest.fixture(scope="module")
def api_db(make_database) -> str:
    return make_database()


@pytest.fixture
def make_client(api_db: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    monkeypatch.setenv("DATABASE_URL", api_db)  # the agent's tools read from here
    clients: list[TestClient] = []

    def make(model: FakeModel | None = None, telegram: bool = True) -> TestClient:
        client = TestClient(app_with_fakes(api_db, model, telegram))
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: Any) -> TestClient:
    return make_client()
