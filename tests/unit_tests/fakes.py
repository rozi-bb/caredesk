"""Fake models and accounts shared by the backend and UI tests."""

import itertools
from typing import Any

from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableLambda

from agent.graph import build_graph
from agent.triage import TriageResult
from backend.config import Settings
from backend.main import create_app

SECRET = "s" * 40
BOT_KEY = "b" * 40
BOT_USERNAME = "caredesk_test_bot"
PETER = "peter.bennett@example.org"  # family, son of Harold Bennett
ANNE = "anne.bennett@example.org"  # family, daughter of Harold Bennett
ANSWER = "Harold has lunch at noon today."


class FakeModel(GenericFakeChatModel):
    """Answering model with scripted replies; accepts tools like a real one."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "FakeModel":
        return self


def answering(*replies: AIMessage, streaming: bool = True) -> FakeModel:
    script = replies or (AIMessage(ANSWER),)
    return FakeModel(messages=itertools.cycle(script), disable_streaming=not streaming)


OUTAGE = "[both classifiers down]"  # a message both fake classifiers fail on


def _label(text: str) -> str:
    if OUTAGE in text:
        raise TimeoutError("fake classifier down")
    text = text.lower()
    return "emergency" if "fell" in text else "clinical" if "dose" in text else "normal"


def by_keyword(messages: list[BaseMessage]) -> TriageResult:
    """Fake fallback classifier."""
    return TriageResult(category=_label(messages[-1].text), reason="test")  # type: ignore[arg-type]


async def jev_by_keyword(text: str) -> dict[str, float]:
    """Fake Jev: certain of the label the keyword rule picks."""
    label = _label(text)
    return {name: float(name == label) for name in ("emergency", "clinical", "normal")}


def app_with_fakes(
    database_url: str, model: FakeModel | None = None, telegram: bool = True
) -> FastAPI:
    """The real backend, with fake models and test secrets."""
    settings = Settings(
        database_url=database_url,
        auth_secret=SECRET,
        token_minutes=5,
        telegram_bot_username=BOT_USERNAME if telegram else None,
        telegram_bot_key=BOT_KEY if telegram else None,
    )
    return create_app(
        lambda cp: build_graph(
            model or answering(), RunnableLambda(by_keyword), cp, jev=jev_by_keyword
        ),
        settings,
    )
