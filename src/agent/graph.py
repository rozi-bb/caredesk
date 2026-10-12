"""CareDesk graph.

Every message goes through triage first (ADR-0006). Emergencies and clinical
questions get fixed responses; everything else reaches the agent, which calls
read-only tools. The Agent Server saves each thread's state.
"""

from __future__ import annotations

import logging
from functools import cache
from typing import Any, NotRequired

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.runtime import Runtime
from langgraph.types import Checkpointer

from agent.context import Context
from agent.db import REFERENCE_DATE
from agent.tools import TOOLS
from agent.triage import (
    CLINICAL_RESPONSE,
    EMERGENCY_RESPONSE,
    NOT_RECORDED,
    RECORDED,
    TRIAGE_PROMPT,
    Route,
    TriageResult,
    keyword_emergency,
    record_emergency,
)

MODEL_NAME = "deepseek-flash"

log = logging.getLogger(__name__)

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

For questions about rights, visiting, belongings and money, choices and privacy, room
changes, complaints, abuse or neglect, restraints and bed rails, billing policy, or
contacts, call search_rules. Answer only from the passages it returns, and cite every
passage you rely on with its label in square brackets, exactly as given, for example
[F563] or [Handbook: Visiting]. If the passages do not answer the question, say you do
not know and suggest asking the front desk. Never cite a source search_rules did not
return, and use square brackets only for those sources, never for records or tools. Explain what the rules require; decisions about a specific resident's care
belong to the care team.

You do not give medical advice, diagnoses, or medication guidance. For anything
medical, refer the person to the nursing staff."""


class State(MessagesState):
    """The conversation, plus the triage outcome for the latest message."""

    route: NotRequired[Route]
    incident_id: NotRequired[int | None]


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


@cache
def default_classifier() -> Runnable[Any, Any]:
    """Return the triage classifier: a quick call that fails fast.

    The short timeout matters: if triage fails, the message is handled as an
    emergency, so a slow provider must not keep someone waiting for minutes.
    JSON mode, because DeepSeek's thinking mode rejects the forced tool call
    that the default structured-output method uses.
    """
    model = ChatDeepSeek(model=MODEL_NAME, temperature=0, max_retries=1, timeout=15)
    return model.with_structured_output(TriageResult, method="json_mode")


def _latest_human_text(messages: list[AnyMessage]) -> str:
    return next((m.text for m in reversed(messages) if isinstance(m, HumanMessage)), "")


def _metadata(ctx: Context) -> RunnableConfig:
    return {"metadata": {"user_id": ctx.user_id, "role": ctx.role}}


def build_graph(
    model: BaseChatModel | None = None,
    classifier: Runnable[Any, Any] | None = None,
    checkpointer: Checkpointer = None,
) -> CompiledStateGraph[State, Context, MessagesState, State]:
    """Build the CareDesk graph.

    Args:
        model: Chat model for answers. Defaults to DeepSeek; tests pass a fake.
        classifier: Triage classifier returning a TriageResult. Defaults to DeepSeek.
        checkpointer: Only for tests that run the graph outside the Agent Server.
            On the server, leave it as None: the server persists threads itself.
    """
    tools = TOOLS

    async def triage(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
        """Route the latest message: emergency, clinical, or normal."""
        ctx = runtime.context or Context()
        text = _latest_human_text(state["messages"])
        if keyword_emergency(text):
            return {"route": "emergency", "incident_id": None}
        try:
            result = await (classifier or default_classifier()).ainvoke(
                [SystemMessage(TRIAGE_PROMPT), HumanMessage(text)],
                config=_metadata(ctx),
            )
            route = TriageResult.model_validate(result).category
        except Exception:
            # Any failure, including a malformed answer: fail toward safety.
            log.exception("Triage failed; handling the message as an emergency")
            route = "emergency"
        return {"route": route, "incident_id": None}

    def emergency_response(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
        """Record the emergency and return fixed instructions."""
        ctx = runtime.context or Context()
        incident = record_emergency(ctx, _latest_human_text(state["messages"]))
        text = EMERGENCY_RESPONSE.format(
            recorded=RECORDED if incident else NOT_RECORDED
        )
        return {"messages": [AIMessage(text)], "incident_id": incident}

    def decline_clinical(state: State) -> dict[str, Any]:
        """Return the fixed decline for medical questions."""
        return {"messages": [AIMessage(CLINICAL_RESPONSE)]}

    async def agent(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
        """Answer the latest message, calling tools when records or rules are needed."""
        ctx = runtime.context or Context()
        llm = (model or default_model()).bind_tools(tools)
        reply = await llm.ainvoke(
            [SystemMessage(system_prompt(ctx)), *state["messages"]],
            config=_metadata(ctx),
        )
        return {"messages": [reply]}

    def after_triage(state: State) -> str:
        return {"emergency": "emergency_response", "clinical": "decline_clinical"}.get(
            state["route"], "agent"
        )

    # Callers send only messages; route and incident_id are set by triage alone.
    builder: StateGraph[State, Context, MessagesState, State] = StateGraph(
        State, input_schema=MessagesState, context_schema=Context
    )
    builder.add_node("triage", triage)
    builder.add_node("emergency_response", emergency_response)
    builder.add_node("decline_clinical", decline_clinical)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "triage")
    builder.add_conditional_edges(
        "triage", after_triage, ["emergency_response", "decline_clinical", "agent"]
    )
    builder.add_edge("emergency_response", END)
    builder.add_edge("decline_clinical", END)
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile(name="CareDesk", checkpointer=checkpointer)


graph = build_graph()
