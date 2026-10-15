from collections.abc import Awaitable, Callable
from typing import Any

import psycopg
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from agent.context import Context
from agent.graph import build_graph
from agent.triage import (
    CLINICAL_RESPONSE,
    EMERGENCY_RESPONSE,
    UNAVAILABLE_RESPONSE,
    TriageResult,
    jev_route,
)

pytestmark = pytest.mark.anyio

Jev = Callable[[str], Awaitable[dict[str, float]]]


class NoCallModel(GenericFakeChatModel):
    """Fails the test if the answering model is ever called."""

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the agent model must not be called")

    def bind_tools(self, tools: Any, **kwargs: Any) -> "NoCallModel":
        return self


def jev_says(label: str, emergency: float | None = None) -> Jev:
    """A fake Jev that ranks `label` first."""
    probabilities = {"emergency": 0.0, "clinical": 0.0, "normal": 0.0}
    probabilities[label] = 1.0
    if emergency is not None:
        probabilities["emergency"] = emergency
        probabilities[label] = 1.0 - emergency

    async def answer(_: str) -> dict[str, float]:
        return probabilities

    return answer


async def jev_down(_: str) -> dict[str, float]:
    raise TimeoutError("Jev did not answer")


def classifier(category: str) -> RunnableLambda[Any, TriageResult]:
    return RunnableLambda(lambda _: TriageResult(category=category, reason="test"))  # type: ignore[arg-type]


def broken(_: Any) -> TriageResult:
    raise TimeoutError("provider down")


UNUSED = RunnableLambda(lambda _: pytest.fail("the fallback must not be called"))


def no_agent() -> NoCallModel:
    return NoCallModel(messages=iter([AIMessage(content="unused")]))


def incident_count(db: str) -> int:
    with psycopg.connect(db) as conn:
        row = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()
        assert row is not None
        return int(row[0])


async def ask(graph: Any, text: str, ctx: Context) -> dict[str, Any]:
    result: dict[str, Any] = await graph.ainvoke(
        {"messages": [HumanMessage(text)]}, context=ctx
    )
    return result


# ---------- the routing rule ----------


def test_top_choice_wins_below_the_threshold() -> None:
    assert jev_route({"emergency": 0.1, "clinical": 0.8, "normal": 0.1}) == "clinical"


def test_emergency_wins_at_the_threshold_even_when_ranked_second() -> None:
    assert jev_route({"emergency": 0.3, "clinical": 0.0, "normal": 0.7}) == "emergency"


def test_unexpected_labels_are_refused() -> None:
    with pytest.raises(ValueError):
        jev_route({"emergency": 0.0, "normal": 1.0})


# ---------- the three paths ----------


async def test_jev_decides_and_the_fallback_is_not_called(db_env: str) -> None:
    graph = build_graph(no_agent(), UNUSED, jev=jev_says("clinical"))
    result = await ask(graph, "Should he take an extra dose?", Context())
    assert (result["route"], result["triage_by"]) == ("clinical", "jev")
    assert result["messages"][-1].text == CLINICAL_RESPONSE


async def test_when_jev_fails_the_fallback_decides(db_env: str) -> None:
    graph = build_graph(no_agent(), classifier("clinical"), jev=jev_down)
    result = await ask(graph, "Should he take an extra dose?", Context())
    assert (result["route"], result["triage_by"]) == ("clinical", "deepseek")


async def test_unexpected_jev_answer_also_goes_to_the_fallback(db_env: str) -> None:
    async def odd(_: str) -> dict[str, float]:
        return {"urgent": 1.0}

    graph = build_graph(no_agent(), classifier("clinical"), jev=odd)
    result = await ask(graph, "Should he take an extra dose?", Context())
    assert (result["route"], result["triage_by"]) == ("clinical", "deepseek")


async def test_when_both_fail_the_user_gets_the_contacts_and_nothing_else(
    db_env: str,
) -> None:
    before = incident_count(db_env)
    graph = build_graph(no_agent(), RunnableLambda(broken), jev=jev_down)
    result = await ask(graph, "My mother is not breathing!", Context())
    assert (result["route"], result["triage_by"]) == ("unavailable", None)
    reply = result["messages"][-1].text
    assert reply == UNAVAILABLE_RESPONSE
    assert "extension 200" in reply and "911" in reply
    assert incident_count(db_env) == before


# ---------- emergencies and fixed replies ----------


async def test_emergency_gets_the_contacts_and_writes_nothing(db_env: str) -> None:
    before = incident_count(db_env)
    graph = build_graph(no_agent(), UNUSED, jev=jev_says("emergency"))
    result = await ask(graph, "My mother is not breathing!", Context())
    assert result["route"] == "emergency"
    reply = result["messages"][-1].text
    assert reply == EMERGENCY_RESPONSE
    assert "extension 200" in reply and "911" in reply
    assert incident_count(db_env) == before


async def test_emergency_ranked_second_by_jev_is_still_an_emergency(
    db_env: str,
) -> None:
    graph = build_graph(no_agent(), UNUSED, jev=jev_says("normal", emergency=0.34))
    result = await ask(
        graph, "I think a staff member was rough with my father", Context()
    )
    assert result["route"] == "emergency"


async def test_emergency_reply_needs_no_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://nobody:wrong@127.0.0.1:1/missing?connect_timeout=1",
    )
    graph = build_graph(no_agent(), UNUSED, jev=jev_says("emergency"))
    result = await ask(graph, "Help, she collapsed", Context())
    assert result["messages"][-1].text == EMERGENCY_RESPONSE


def test_callers_can_only_send_messages() -> None:
    graph = build_graph(no_agent(), UNUSED, jev=jev_says("normal"))
    assert set(graph.get_input_jsonschema()["properties"]) == {"messages"}
    assert {"route", "triage_by"} <= set(graph.get_output_jsonschema()["properties"])


async def test_route_sent_by_caller_is_ignored(db_env: str) -> None:
    graph = build_graph(no_agent(), UNUSED, jev=jev_says("clinical"))
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage("Should he take an extra dose?")],
            "route": "normal",
        },
        context=Context(),
    )
    assert result["route"] == "clinical"


class AnsweringModel(GenericFakeChatModel):
    """Fake agent model that accepts tools and returns scripted answers."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "AnsweringModel":
        return self


async def test_normal_question_reaches_the_agent(db_env: str) -> None:
    agent = AnsweringModel(messages=iter([AIMessage(content="Here is the schedule.")]))
    graph = build_graph(agent, UNUSED, jev=jev_says("normal"))
    result = await ask(graph, "What's on today?", Context())
    assert result["route"] == "normal"
    assert result["messages"][-1].text == "Here is the schedule."
