import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent.graph import build_graph, default_classifier
from agent.triage import TRIAGE_PROMPT, TriageResult, jev_probabilities, jev_route

pytestmark = pytest.mark.anyio


@pytest.mark.langsmith
async def test_remembers_name_from_earlier_turn() -> None:
    graph = build_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "integration-memory"}}

    await graph.ainvoke({"messages": [HumanMessage("Hi, my name is Rozi.")]}, config)
    result = await graph.ainvoke(
        {"messages": [HumanMessage("What is my name?")]}, config
    )

    assert "rozi" in result["messages"][-1].text.lower()


async def test_real_jev_answers_instead_of_falling_back() -> None:
    """A broken Jev setup is hidden by the fallback, so call it directly."""
    probabilities = await jev_probabilities("When is the morning medication round?")
    assert jev_route(probabilities) == "normal"


async def test_real_classifier_answers_instead_of_failing_safe() -> None:
    """A broken classifier is hidden by the fail-safe, so call it directly."""
    result = await default_classifier().ainvoke(
        [
            SystemMessage(TRIAGE_PROMPT),
            HumanMessage("When is the morning medication round?"),
        ]
    )
    assert TriageResult.model_validate(result).category == "normal"
