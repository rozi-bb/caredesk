"""Tests for the chat UI: its backend client, and that it cannot reach model keys.

The client runs against the real backend app in process, with fake models.
"""

import ast
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from chainlit.types import Pagination, ThreadFilter
from chainlit.user import User

from ui import telegram_link as tg
from ui.client import (
    BackendClient,
    ConnectLink,
    ConversationNotFound,
    SignInRequired,
    TelegramStatus,
    TelegramUnavailable,
)
from ui.data_layer import BackendDataLayer

from .fakes import ANNE, ANSWER, BOT_KEY, PETER, app_with_fakes

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


# ---------- sidebar history: each user sees only their own (ADR-0025) ----------


async def _signed_in(
    layer: BackendDataLayer, backend: BackendClient, email: str, password: str
) -> str:
    token = await backend.login(email, password)
    assert token
    await layer.create_user(User(identifier=email, metadata={"token": token}))
    return token


async def _sidebar(layer: BackendDataLayer, email: str) -> list[str]:
    page = await layer.list_threads(Pagination(first=20), ThreadFilter(userId=email))
    return [t["id"] for t in page.data]


async def test_sidebar_shows_only_the_signed_in_users_threads(
    backend: BackendClient, test_password: str
) -> None:
    layer = BackendDataLayer(backend)
    peter = await _signed_in(layer, backend, PETER, test_password)
    anne = await _signed_in(layer, backend, ANNE, test_password)
    peters = await backend.new_thread(peter)
    [e async for e in backend.ask(peter, peters, "What is Harold doing?")]
    annes = await backend.new_thread(anne)
    [e async for e in backend.ask(anne, annes, "Can I visit tonight?")]

    assert await _sidebar(layer, PETER) == [peters]
    assert await _sidebar(layer, ANNE) == [annes]
    assert await _sidebar(layer, "nobody@example.org") == []


async def test_a_thread_belongs_only_to_its_owner(
    backend: BackendClient, test_password: str
) -> None:
    layer = BackendDataLayer(backend)
    peter = await _signed_in(layer, backend, PETER, test_password)
    await _signed_in(layer, backend, ANNE, test_password)
    thread = await backend.new_thread(peter)
    [e async for e in backend.ask(peter, thread, "What is Harold doing?")]

    # Unknown until the backend has confirmed the owner: Chainlit then answers 404.
    assert await layer.get_thread_author(thread) == ""
    assert await layer.get_thread(thread) is None

    await _sidebar(layer, PETER)
    # Chainlit compares this with the signed-in user, so Anne is refused.
    assert await layer.get_thread_author(thread) == PETER
    loaded = await layer.get_thread(thread)
    assert loaded is not None
    assert loaded["userIdentifier"] == PETER
    assert [(s["type"], s["output"]) for s in loaded["steps"]] == [
        ("user_message", "What is Harold doing?"),
        ("assistant_message", ANSWER),
    ]


async def test_deleting_from_the_sidebar_deletes_in_the_backend(
    backend: BackendClient, test_password: str
) -> None:
    layer = BackendDataLayer(backend)
    peter = await _signed_in(layer, backend, PETER, test_password)
    thread = await backend.new_thread(peter)
    [e async for e in backend.ask(peter, thread, "What is Harold doing?")]
    await _sidebar(layer, PETER)

    await layer.delete_thread(thread)
    assert await _sidebar(layer, PETER) == []
    with pytest.raises(ConversationNotFound):
        await backend.history(peter, thread)


async def test_the_backend_token_is_not_handed_back_to_chainlit(
    backend: BackendClient, test_password: str
) -> None:
    layer = BackendDataLayer(backend)
    token = await backend.login(PETER, test_password)
    persisted = await layer.create_user(
        User(identifier=PETER, metadata={"token": token, "role": "family"})
    )
    assert persisted is not None
    assert "token" not in persisted.metadata  # Chainlit returns this user to the page
    assert layer.token_for(PETER) == token
    assert await layer.get_user(PETER) is None


# ---------- connecting Telegram (ADR-0027) ----------


async def test_connect_check_and_disconnect_telegram(
    make_database, monkeypatch: pytest.MonkeyPatch, test_password: str
) -> None:
    url = make_database()
    monkeypatch.setenv("DATABASE_URL", url)
    app = app_with_fakes(url)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        backend = BackendClient("http://backend", transport=transport)
        token = await backend.login(PETER, test_password)
        assert token
        assert await backend.telegram_status(token) == TelegramStatus(
            available=True, connected=False
        )
        link = await backend.telegram_link(token)
        code = link.link.rsplit("start=", 1)[1]

        # The bot's side, as the real bot will call it.
        async with httpx.AsyncClient(
            transport=transport, base_url="http://backend"
        ) as bot:
            response = await bot.post(
                "/telegram/connect",
                headers={"X-Bot-Key": BOT_KEY},
                json={
                    "code": code,
                    "telegram_user_id": 77,
                    "telegram_username": "pete",
                },
            )
            assert response.status_code == 200

        status = await backend.telegram_status(token)
        assert (status.connected, status.username) == (True, "pete")
        await backend.disconnect_telegram(token)
        assert (await backend.telegram_status(token)).connected is False


async def test_telegram_not_set_up_is_reported(
    make_database, monkeypatch: pytest.MonkeyPatch, test_password: str
) -> None:
    url = make_database()
    monkeypatch.setenv("DATABASE_URL", url)
    app = app_with_fakes(url, telegram=False)
    async with app.router.lifespan_context(app):
        backend = BackendClient(
            "http://backend", transport=httpx.ASGITransport(app=app)
        )
        token = await backend.login(PETER, test_password)
        assert token
        assert (await backend.telegram_status(token)).available is False
        with pytest.raises(TelegramUnavailable):
            await backend.telegram_link(token)


def test_status_text_shows_who_is_connected() -> None:
    assert tg.status_text(TelegramStatus(True, False)) == "Telegram is not connected."
    assert "@pete" in tg.status_text(TelegramStatus(True, True, "pete"))
    assert "a Telegram account" in tg.status_text(TelegramStatus(True, True, None))


def test_link_text_and_qr_code_carry_the_link() -> None:
    link = ConnectLink(link="https://t.me/caredesk_test_bot?start=abc", expires_at="")
    assert link.link in tg.link_text(link)
    assert "expires in 10 minutes" in tg.link_text(link)
    assert tg.qr_png(link.link).startswith(b"\x89PNG")


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
