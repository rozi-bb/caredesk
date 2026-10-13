"""Tests for the chat UI: its backend client, and that it cannot reach model keys.

The client runs against the real backend app in process, with fake models.
"""

import ast
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from ui.client import BackendClient, ConversationNotFound, SignInRequired

from .fakes import ANNE, ANSWER, PETER, app_with_fakes

pytestmark = pytest.mark.anyio

UI_DIR = Path(__file__).resolve().parents[2] / "src" / "ui"


@pytest.fixture
async def backend(
    make_database, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[BackendClient]:
    url = make_database()
    monkeypatch.setenv("DATABASE_URL", url)
    app = app_with_fakes(url)
    async with app.router.lifespan_context(app):
        yield BackendClient("http://backend", transport=httpx.ASGITransport(app=app))


async def test_sign_in_and_profile(backend: BackendClient, test_password: str) -> None:
    token = await backend.login(PETER, test_password)
    assert token
    profile = await backend.profile(token)
    assert (profile.name, profile.role) == ("Peter Bennett", "family")
    assert await backend.login(PETER, "wrong-password") is None


async def test_ask_streams_events_and_the_thread_can_be_resumed(
    backend: BackendClient, test_password: str
) -> None:
    token = await backend.login(PETER, test_password)
    assert token
    thread = await backend.new_thread(token)
    events = [e async for e in backend.ask(token, thread, "What is Harold doing?")]
    assert "".join(d["text"] for e, d in events if e == "token") == ANSWER
    assert events[-1] == ("done", {"route": "normal"})

    listed = await backend.threads(token)
    assert [(t.id, t.title) for t in listed] == [(thread, "What is Harold doing?")]
    assert await backend.history(token, thread) == [
        ("user", "What is Harold doing?"),
        ("assistant", ANSWER),
    ]


async def test_expired_sign_in_is_reported(backend: BackendClient) -> None:
    with pytest.raises(SignInRequired):
        await backend.threads("not-a-token")
    with pytest.raises(SignInRequired):
        [
            e
            async for e in backend.ask(
                "not-a-token", "00000000-0000-0000-0000-000000000000", "hi"
            )
        ]


async def test_someone_elses_thread_is_not_found(
    backend: BackendClient, test_password: str
) -> None:
    peter = await backend.login(PETER, test_password)
    anne = await backend.login(ANNE, test_password)
    assert peter and anne
    thread = await backend.new_thread(peter)
    with pytest.raises(ConversationNotFound):
        await backend.history(anne, thread)
    with pytest.raises(ConversationNotFound):
        [e async for e in backend.ask(anne, thread, "hi")]


# ---------- the UI never holds model keys (step 19) ----------


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_ui_code_cannot_reach_models_or_the_database() -> None:
    forbidden = ("agent", "backend", "langchain", "langgraph", "psycopg")
    for path in UI_DIR.glob("*.py"):
        reached = {m for m in _imports(path) if m.split(".")[0] in forbidden}
        assert not reached, f"{path.name} imports {reached}"


def test_ui_environment_holds_no_backend_secrets() -> None:
    names = {
        line.split("=", 1)[0]
        for line in (UI_DIR / ".env.example").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    }
    # DATABASE_URL would also switch on Chainlit's own data layer.
    assert names == {"BACKEND_URL", "CHAINLIT_AUTH_SECRET"}
