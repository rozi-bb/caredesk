from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatResult
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field

from agent.context import Context
from agent.graph import build_graph
from agent.tools import TOOLS
from agent.triage import TriageResult

pytestmark = pytest.mark.anyio


class RecordingModel(GenericFakeChatModel):
    """Fake model that remembers every list of messages it was given."""

    seen: list[list[BaseMessage]] = Field(default_factory=list)

    def _generate(
        self, messages: list[BaseMessage], *args: Any, **kwargs: Any
    ) -> ChatResult:
        self.seen.append(list(messages))
        return super()._generate(messages, *args, **kwargs)

    def bind_tools(self, tools: Any, **kwargs: Any) -> "RecordingModel":
        return self


def replies(*messages: str | AIMessage) -> Iterator[AIMessage]:
    return iter(
        m if isinstance(m, AIMessage) else AIMessage(content=m) for m in messages
    )


NORMAL = RunnableLambda(lambda _: TriageResult(category="normal", reason="test"))


def thread(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def call(tool: str, **args: str) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": tool, "args": args, "id": "call-1"}]
    )


async def test_second_turn_sees_the_first_turn() -> None:
    model = RecordingModel(
        messages=replies("Nice to meet you, Rozi.", "Your name is Rozi.")
    )
    graph = build_graph(model, NORMAL, checkpointer=InMemorySaver())

    await graph.ainvoke({"messages": [HumanMessage("My name is Rozi.")]}, thread("a"))
    await graph.ainvoke({"messages": [HumanMessage("What is my name?")]}, thread("a"))

    second_call = model.seen[1]
    assert isinstance(second_call[0], SystemMessage)
    assert [m.content for m in second_call[1:]] == [
        "My name is Rozi.",
        "Nice to meet you, Rozi.",
        "What is my name?",
    ]


async def test_threads_do_not_share_history() -> None:
    model = RecordingModel(messages=replies("Hello.", "Hello again."))
    graph = build_graph(model, NORMAL, checkpointer=InMemorySaver())

    await graph.ainvoke({"messages": [HumanMessage("My name is Rozi.")]}, thread("a"))
    await graph.ainvoke({"messages": [HumanMessage("What is my name?")]}, thread("b"))

    assert [m.content for m in model.seen[1][1:]] == ["What is my name?"]


def test_the_model_cannot_set_identity_through_tool_arguments() -> None:
    for tool in TOOLS:
        fields = set(tool.tool_call_schema.model_json_schema().get("properties", {}))
        assert not fields & {"runtime", "user_id", "role", "context"}, tool.name


async def test_tools_use_the_identity_from_the_run_context(db_env: str) -> None:
    with psycopg.connect(db_env) as conn:
        ids = dict(conn.execute("SELECT full_name, id FROM family_members").fetchall())

    async def billing_reply(user: str) -> str:
        model = RecordingModel(
            messages=replies(call("get_billing", resident="Harold Bennett"), "Done.")
        )
        result = await build_graph(model, NORMAL).ainvoke(
            {"messages": [HumanMessage("Show Harold's bill.")]},
            context=Context(user_id=ids[user], role="family"),
        )
        return next(m.content for m in result["messages"] if isinstance(m, ToolMessage))

    assert "permission" in await billing_reply("Anne Bennett")
    assert "$5,600.00" in await billing_reply("Peter Bennett")
