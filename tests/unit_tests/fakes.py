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


def by_keyword(messages: list[BaseMessage]) -> TriageResult:
    text = messages[-1].text.lower()
    category = (
        "emergency" if "fell" in text else "clinical" if "dose" in text else "normal"
    )
    return TriageResult(category=category, reason="test")  # type: ignore[arg-type]


def app_with_fakes(database_url: str, model: FakeModel | None = None) -> FastAPI:
    """The real backend, with fake models and a test signing secret."""
    settings = Settings(database_url=database_url, auth_secret=SECRET, token_minutes=5)
    return create_app(
        lambda cp: build_graph(model or answering(), RunnableLambda(by_keyword), cp),
        settings,
    )
