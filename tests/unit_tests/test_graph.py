from collections.abc import Iterator
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field

from agent.graph import SYSTEM_PROMPT, build_graph

pytestmark = pytest.mark.anyio


class RecordingModel(GenericFakeChatModel):
    """Fake model that remembers every list of messages it was given."""

    seen: list[list[BaseMessage]] = Field(default_factory=list)

    def _generate(
        self, messages: list[BaseMessage], *args: Any, **kwargs: Any
    ) -> ChatResult:
        self.seen.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


def replies(*texts: str) -> Iterator[AIMessage]:
    return iter(AIMessage(content=t) for t in texts)


def thread(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


async def test_second_turn_sees_the_first_turn() -> None:
    model = RecordingModel(
        messages=replies("Nice to meet you, Rozi.", "Your name is Rozi.")
    )
    graph = build_graph(model, checkpointer=InMemorySaver())

    await graph.ainvoke({"messages": [HumanMessage("My name is Rozi.")]}, thread("a"))
    await graph.ainvoke({"messages": [HumanMessage("What is my name?")]}, thread("a"))

    second_call = model.seen[1]
    assert isinstance(second_call[0], SystemMessage)
    assert second_call[0].content == SYSTEM_PROMPT
    assert [m.content for m in second_call[1:]] == [
        "My name is Rozi.",
        "Nice to meet you, Rozi.",
        "What is my name?",
    ]


async def test_threads_do_not_share_history() -> None:
    model = RecordingModel(messages=replies("Hello.", "Hello again."))
    graph = build_graph(model, checkpointer=InMemorySaver())

    await graph.ainvoke({"messages": [HumanMessage("My name is Rozi.")]}, thread("a"))
    await graph.ainvoke({"messages": [HumanMessage("What is my name?")]}, thread("b"))

    assert [m.content for m in model.seen[1][1:]] == ["What is my name?"]
