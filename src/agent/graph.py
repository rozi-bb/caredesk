"""CareDesk graph.

Feature 9.1: one model call over the whole conversation so far. The Agent
Server saves each thread's messages, so earlier turns are remembered.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

MODEL_NAME = "deepseek-flash"

SYSTEM_PROMPT = """\
You are CareDesk, the administrative assistant of Evergreen Care Home, a nursing home.
You help staff and family members with everyday administrative questions.
Answer in English, briefly and politely.

You cannot look up the home's records yet: schedules, activities, visits, incidents,
and billing are not available to you. If someone asks about them, say you cannot look
that up yet. Never guess or invent details about residents, staff, or the home.

You do not give medical advice, diagnoses, or medication guidance. For anything
medical, refer the person to the nursing staff."""


@cache
def default_model() -> BaseChatModel:
    """Return the DeepSeek model, created on first use.

    Created lazily because ChatDeepSeek refuses to start without an API key,
    and unit tests run without one.
    """
    return ChatDeepSeek(model=MODEL_NAME, temperature=0, max_retries=2, timeout=60)


def build_graph(
    model: BaseChatModel | None = None, checkpointer: Checkpointer = None
) -> CompiledStateGraph[MessagesState, None, MessagesState, MessagesState]:
    """Build the CareDesk graph.

    Args:
        model: Chat model to use. Defaults to DeepSeek; tests pass a fake model.
        checkpointer: Only for tests that run the graph outside the Agent Server.
            On the server, leave it as None: the server persists threads itself.
    """

    async def call_model(state: MessagesState) -> dict[str, Any]:
        """Answer the latest message, given the whole conversation."""
        llm = model or default_model()
        reply = await llm.ainvoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [reply]}

    builder: StateGraph[MessagesState, None, MessagesState, MessagesState] = StateGraph(
        MessagesState
    )
    builder.add_node(call_model)
    builder.add_edge(START, "call_model")
    return builder.compile(name="CareDesk", checkpointer=checkpointer)


graph = build_graph()
