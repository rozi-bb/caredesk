import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent.graph import build_graph

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
