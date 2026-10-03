"""CareDesk graph.

The agent answers from the conversation so far and calls read-only tools
for the home's records. The Agent Server saves each thread's messages.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.runtime import Runtime
from langgraph.types import Checkpointer

from agent.context import Context
from agent.db import REFERENCE_DATE
from agent.tools import RECORD_TOOLS

MODEL_NAME = "deepseek-flash"

_AUDIENCE = {
    "staff": "a staff member of the home",
    "family": "a family member of a resident",
    "unknown": "a user whose identity is unknown",
}

SYSTEM_PROMPT = """\
You are CareDesk, the administrative assistant of Evergreen Care Home, a nursing home.
You help staff and family members with everyday administrative questions.
Answer in English, briefly and politely.

Today is {today}. You are talking to {audience}.

Use the tools to look up residents, schedules, activities, visits, incidents, and billing.
Only state facts that a tool returned. Never guess or invent details about residents,
staff, or the home. If a tool says the user cannot see something, tell them plainly
and do not try to get around it. If a name matches several residents, ask which one.

You cannot look up the home's policies or regulations yet. If asked, say so.

You do not give medical advice, diagnoses, or medication guidance. For anything
medical, refer the person to the nursing staff."""


def system_prompt(ctx: Context) -> str:
    """Return the system prompt for this caller."""
    return SYSTEM_PROMPT.format(
        today=f"{REFERENCE_DATE:%A %d %B %Y}", audience=_AUDIENCE[ctx.role]
    )


@cache
def default_model() -> BaseChatModel:
    """Return the DeepSeek model, created on first use.

    Created lazily because ChatDeepSeek refuses to start without an API key,
    and unit tests run without one.
    """
    return ChatDeepSeek(model=MODEL_NAME, temperature=0, max_retries=2, timeout=60)


def build_graph(
    model: BaseChatModel | None = None, checkpointer: Checkpointer = None
) -> CompiledStateGraph[MessagesState, Context, MessagesState, MessagesState]:
    """Build the CareDesk graph.

    Args:
        model: Chat model to use. Defaults to DeepSeek; tests pass a fake model.
        checkpointer: Only for tests that run the graph outside the Agent Server.
            On the server, leave it as None: the server persists threads itself.
    """
    tools = RECORD_TOOLS

    async def agent(state: MessagesState, runtime: Runtime[Context]) -> dict[str, Any]:
        """Answer the latest message, calling tools when records are needed."""
        ctx = runtime.context or Context()
        llm = (model or default_model()).bind_tools(tools)
        reply = await llm.ainvoke(
            [SystemMessage(system_prompt(ctx)), *state["messages"]],
            config={"metadata": {"user_id": ctx.user_id, "role": ctx.role}},
        )
        return {"messages": [reply]}

    builder: StateGraph[MessagesState, Context, MessagesState, MessagesState] = (
        StateGraph(MessagesState, context_schema=Context)
    )
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile(name="CareDesk", checkpointer=checkpointer)


graph = build_graph()
