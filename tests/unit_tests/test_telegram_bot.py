"""Tests for the Telegram bot: its replies, formatting, and what it cannot reach.

The relay talks to the real backend in process, with fake models. Nothing
calls Telegram.
"""

import ast
import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from telegram import Chat, Message, MessageEntity, Update, User
from telegram.ext import Application

from agent.triage import EMERGENCY_NOTICE
from telegram_bot import format as tg_format
from telegram_bot.backend import BotBackend, BotKeyRejected
from telegram_bot.bot import build
from telegram_bot.relay import (
    CUT_OFF,
    DISCONNECTED,
    INVALID_LINK,
    NEW_SESSION,
    TOO_LONG,
    UNREACHABLE,
    Relay,
)
from telegram_bot.streaming import AnswerStream
from ui.client import BackendClient

from .fakes import ANSWER, BOT_KEY, PETER, app_with_fakes

BOT_DIR = Path(__file__).resolve().parents[2] / "src" / "telegram_bot"
PETER_TG = 5001


@pytest.fixture
async def app(make_database, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[object]:
    url = make_database()
    monkeypatch.setenv("DATABASE_URL", url)
    backend_app = app_with_fakes(url)
    async with backend_app.router.lifespan_context(backend_app):
        yield backend_app


def _relay(app: object, key: str = BOT_KEY) -> Relay:
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    return Relay(BotBackend("http://backend", key, transport=transport))


async def _connect_code(app: object, password: str) -> str:
    web = BackendClient("http://backend", transport=httpx.ASGITransport(app=app))  # type: ignore[arg-type]
    token = await web.login(PETER, password)
    assert token
    return (await web.telegram_link(token)).link.rsplit("start=", 1)[1]


# ---------- business flow (step 18) ----------


@pytest.mark.anyio
async def test_connect_chat_new_and_disconnect(app: object, test_password: str) -> None:
    relay = _relay(app)
    welcome = await relay.start(
        PETER_TG, "pete", await _connect_code(app, test_password)
    )
    assert "Hi Peter Bennett" in welcome and EMERGENCY_NOTICE in welcome
    assert await relay.message(PETER_TG, "What is Harold doing today?") == ANSWER
    assert "connected as Peter Bennett" in await relay.help(PETER_TG)
    assert await relay.new(PETER_TG) == NEW_SESSION
    assert await relay.disconnect(PETER_TG) == DISCONNECTED
    after = await relay.message(PETER_TG, "What is Harold doing today?")
    assert ANSWER not in after and "Connect Telegram" in after


@pytest.mark.anyio
async def test_start_without_a_code_explains_how_to_connect(app: object) -> None:
    reply = await _relay(app).start(PETER_TG, None, None)
    assert "Connect Telegram" in reply
    assert EMERGENCY_NOTICE in reply  # the backend's single copy of the contacts


# ---------- security and safety (step 19) ----------


@pytest.mark.anyio
async def test_not_connected_users_get_contacts_but_no_answer(app: object) -> None:
    relay = _relay(app)
    for reply in (
        await relay.message(4242, "What is Harold doing today?"),
        await relay.new(4242),
        await relay.help(4242),
    ):
        assert ANSWER not in reply
        assert EMERGENCY_NOTICE in reply


@pytest.mark.anyio
async def test_a_bad_link_is_refused(app: object) -> None:
    relay = _relay(app)
    for code in ("made-up", "x" * 100):
        assert await relay.start(PETER_TG, None, code) == INVALID_LINK


@pytest.mark.anyio
async def test_a_wrong_bot_key_is_an_error_not_an_answer(app: object) -> None:
    with pytest.raises(BotKeyRejected):
        await _relay(app, key="wrong-" + "k" * 40).message(PETER_TG, "hi")


@pytest.mark.anyio
async def test_backend_down_still_shows_the_emergency_line() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    relay = Relay(
        BotBackend("http://backend", BOT_KEY, transport=httpx.MockTransport(refuse))
    )
    for reply in (
        await relay.message(PETER_TG, "My mother fell"),
        await relay.start(PETER_TG, None, None),
        await relay.start(PETER_TG, None, "code"),
    ):
        assert reply == UNREACHABLE and "911" in reply


@pytest.mark.anyio
async def test_too_long_messages_are_refused_before_the_backend() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the backend must not be called")

    relay = Relay(
        BotBackend("http://backend", BOT_KEY, transport=httpx.MockTransport(fail))
    )
    assert await relay.message(PETER_TG, "x" * 4001) == TOO_LONG


class _SlowBackend(BotBackend):
    """Holds one user's answer until released, to see whether others wait."""

    def __init__(self) -> None:
        super().__init__("http://unused", BOT_KEY)
        self.release = asyncio.Event()

    async def ask(self, telegram_user_id: int, content: str) -> AsyncIterator[str]:
        if telegram_user_id == 1:
            await self.release.wait()
        yield f"answer for {telegram_user_id}"


@pytest.mark.anyio
async def test_one_slow_answer_does_not_hold_up_another_user() -> None:
    backend = _SlowBackend()
    relay = Relay(backend)
    slow = asyncio.create_task(relay.message(1, "a long question"))
    await asyncio.sleep(0)
    # Another user's message (it could be an emergency) is answered meanwhile.
    assert (
        await asyncio.wait_for(relay.message(2, "help, she fell"), 1) == "answer for 2"
    )
    assert not slow.done()
    backend.release.set()
    assert await slow == "answer for 1"


def _app_offline() -> Application:  # type: ignore[type-arg]
    app = build("123:test", _relay(object()))
    # Normally filled in from Telegram when the bot starts; commands need it.
    app.bot._bot_user = User(
        id=99, first_name="CareDesk", is_bot=True, username="caredesk_test_bot"
    )
    return app


def _update(app: Application, chat_type: str, text: str) -> Update:  # type: ignore[type-arg]
    entities = (
        [MessageEntity(MessageEntity.BOT_COMMAND, 0, len(text.split()[0]))]
        if text.startswith("/")
        else []
    )
    message = Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=-100 if chat_type != "private" else 7, type=chat_type),
        from_user=User(id=7, first_name="Pete", is_bot=False),
        text=text,
        entities=entities,
    )
    message.set_bot(app.bot)
    update = Update(update_id=1, message=message)
    update.set_bot(app.bot)
    return update


@pytest.mark.parametrize("text", ["What is Harold doing today?", "/start", "/new"])
def test_the_bot_answers_only_in_private_chats(text: str) -> None:
    app = _app_offline()
    for chat_type, expected in (
        ("private", True),
        ("group", False),
        ("supergroup", False),
    ):
        update = _update(app, chat_type, text)
        handled = any(h.check_update(update) for h in app.handlers[0])
        assert handled is expected, (chat_type, text)


# ---------- streaming (ADR-0028) ----------


@pytest.mark.anyio
async def test_answers_arrive_piece_by_piece(app: object, test_password: str) -> None:
    relay = _relay(app)
    await relay.start(PETER_TG, None, await _connect_code(app, test_password))
    pieces = [p async for p in relay.stream(PETER_TG, "What is Harold doing today?")]
    assert len(pieces) > 1
    assert "".join(pieces) == ANSWER


class _CutOffBackend(BotBackend):
    def __init__(self) -> None:
        super().__init__("http://unused", BOT_KEY)

    async def ask(self, telegram_user_id: int, content: str) -> AsyncIterator[str]:
        yield "Harold has"
        raise httpx.ReadError("connection lost")


@pytest.mark.anyio
async def test_an_answer_cut_off_midway_says_so() -> None:
    answer = await Relay(_CutOffBackend()).message(PETER_TG, "hi")
    assert answer == f"Harold has\n\n{CUT_OFF}"


class _Telegram:
    """Records drafts and messages, with a clock the test moves."""

    def __init__(self, refuse_drafts: bool = False) -> None:
        self.now = 0.0
        self.drafts: list[tuple[int, str]] = []
        self.messages: list[str] = []
        self.refuse_drafts = refuse_drafts

    async def draft(self, draft_id: int, text: str) -> None:
        if self.refuse_drafts:
            raise RuntimeError("drafts not supported")
        self.drafts.append((draft_id, text))

    async def send(self, text: str) -> None:
        self.messages.append(text)

    def stream(self) -> AnswerStream:
        return AnswerStream(self.draft, self.send, every=1.0, clock=lambda: self.now)


@pytest.mark.anyio
async def test_the_draft_grows_at_most_once_a_second_then_the_answer_is_sent() -> None:
    tg = _Telegram()
    stream = tg.stream()
    for now, so_far in (
        (0.0, "Harold"),
        (0.5, "Harold has"),
        (1.2, "Harold has lunch"),
    ):
        tg.now = now
        await stream.update(so_far)
    assert [text for _, text in tg.drafts] == ["Harold", "Harold has lunch"]
    assert len({draft_id for draft_id, _ in tg.drafts}) == 1  # one draft, animated
    assert tg.messages == []  # nothing stays in the chat until the end
    await stream.finish("Harold has lunch at noon.")
    assert tg.messages == ["Harold has lunch at noon."]


@pytest.mark.anyio
async def test_a_long_answer_is_sent_in_parts_as_they_complete() -> None:
    tg = _Telegram()
    stream = tg.stream()
    paragraphs = [f"Part {i}. " + "word " * 400 for i in range(4)]
    answer = ""
    for i, paragraph in enumerate(paragraphs):
        answer = f"{answer}\n\n{paragraph}" if answer else paragraph
        tg.now = float(i * 2)
        await stream.update(answer)
    sent_while_streaming = len(tg.messages)
    assert sent_while_streaming >= 1
    await stream.finish(answer)
    assert tg.messages == tg_format.split(answer)  # every part once, in order
    assert len({draft_id for draft_id, _ in tg.drafts}) > 1  # a new draft per part


@pytest.mark.anyio
async def test_if_drafts_are_refused_the_answer_still_arrives() -> None:
    tg = _Telegram(refuse_drafts=True)
    stream = tg.stream()
    for now in (0.0, 2.0, 4.0):
        tg.now = now
        await stream.update("Harold has lunch")
    await stream.finish("Harold has lunch at noon.")
    assert tg.messages == ["Harold has lunch at noon."]


# ---------- formatting ----------


def test_markdown_becomes_telegram_html() -> None:
    html = tg_format.to_html(
        "## Visiting\n**Bold**, *italic*, `code`, [rules](https://example.org/a?b=1&c=2)\n"
        "- one\n- two\nA <script> tag & more"
    )
    assert html.splitlines() == [
        "<b>Visiting</b>",
        '<b>Bold</b>, <i>italic</i>, <code>code</code>, <a href="https://example.org/a?b=1&amp;c=2">rules</a>',
        "• one",
        "• two",
        "A &lt;script&gt; tag &amp; more",
    ]


def test_tables_stay_monospaced() -> None:
    html = tg_format.to_html("Schedule:\n| Time | What |\n|---|---|\n| 9:00 | Bingo |")
    assert html == "Schedule:\n<pre>| Time | What |\n|---|---|\n| 9:00 | Bingo |</pre>"


def test_long_answers_are_split_under_telegrams_limit() -> None:
    paragraphs = [f"Paragraph {i}. " + "word " * 150 for i in range(30)]
    text = "\n\n".join(paragraphs)
    pieces = tg_format.split(text)
    assert len(pieces) > 1
    assert all(len(p) <= tg_format.CHUNK for p in pieces)
    assert "\n\n".join(pieces) == text
    assert all(len(p) <= tg_format.CHUNK for p in tg_format.split("x" * 10_000))


# ---------- the bot never holds model keys (step 19) ----------


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_bot_code_cannot_reach_models_or_the_database() -> None:
    forbidden = ("agent", "backend", "ui", "langchain", "langgraph", "psycopg")
    for path in BOT_DIR.glob("*.py"):
        reached = {m for m in _imports(path) if m.split(".")[0] in forbidden}
        assert not reached, f"{path.name} imports {reached}"


def test_bot_environment_holds_only_its_own_settings() -> None:
    names = {
        line.split("=", 1)[0]
        for line in (BOT_DIR / ".env.example").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    }
    assert names == {"BACKEND_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_KEY"}
