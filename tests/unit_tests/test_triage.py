import sqlite3
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from agent.context import Context
from agent.graph import build_graph
from agent.triage import CLINICAL_RESPONSE, NOT_RECORDED, RECORDED, TriageResult

pytestmark = pytest.mark.anyio


class NoCallModel(GenericFakeChatModel):
    """Fails the test if the answering model is ever called."""

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the agent model must not be called")

    def bind_tools(self, tools: Any, **kwargs: Any) -> "NoCallModel":
        return self


def classifier(category: str) -> RunnableLambda[Any, TriageResult]:
    return RunnableLambda(lambda _: TriageResult(category=category, reason="test"))  # type: ignore[arg-type]


def broken(_: Any) -> TriageResult:
    raise TimeoutError("provider down")


def no_agent() -> NoCallModel:
    return NoCallModel(messages=iter([AIMessage(content="unused")]))


def family_id(db: Path, name: str) -> int:
    with sqlite3.connect(db) as conn:
        return int(
            conn.execute(
                "SELECT id FROM family_members WHERE full_name = ?", (name,)
            ).fetchone()[0]
        )


def incident(db: Path, incident_id: int) -> tuple[Any, ...]:
    with sqlite3.connect(db) as conn:
        return tuple(
            conn.execute(
                "SELECT resident_id, reported_by_staff_id, category, status, description "
                "FROM incidents WHERE id = ?",
                (incident_id,),
            ).fetchone()
        )


async def ask(graph: Any, text: str, ctx: Context) -> dict[str, Any]:
    result: dict[str, Any] = await graph.ainvoke(
        {"messages": [HumanMessage(text)]}, context=ctx
    )
    return result


async def test_keyword_emergency_needs_no_model_and_is_recorded(db_env: Path) -> None:
    graph = build_graph(no_agent(), RunnableLambda(broken))
    karen = Context(user_id=family_id(db_env, "Karen Mitchell"), role="family")

    result = await ask(graph, "My mother is not breathing!", karen)

    assert result["route"] == "emergency"
    assert (
        "911" in result["messages"][-1].text and RECORDED in result["messages"][-1].text
    )
    resident, reporter, category, status, text = incident(db_env, result["incident_id"])
    assert (category, status, reporter) == ("emergency", "needs_action", None)
    assert resident is not None  # Karen is linked to exactly one resident
    assert "not breathing" in text


async def test_resident_left_empty_when_it_cannot_be_known(db_env: Path) -> None:
    graph = build_graph(no_agent(), classifier("emergency"))
    linda = Context(
        user_id=family_id(db_env, "Linda Moreno"), role="family"
    )  # two residents
    result = await ask(graph, "Something is very wrong, please send someone", linda)
    assert incident(db_env, result["incident_id"])[0] is None


async def test_triage_failure_is_treated_as_emergency(db_env: Path) -> None:
    graph = build_graph(no_agent(), RunnableLambda(broken))
    result = await ask(graph, "Can you help me with something?", Context())
    assert result["route"] == "emergency"


async def test_emergency_reply_survives_a_database_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CAREDESK_DB_PATH", str(tmp_path / "missing.db"))
    graph = build_graph(no_agent(), classifier("emergency"))
    result = await ask(graph, "Help, she collapsed", Context())
    assert result["incident_id"] is None
    assert NOT_RECORDED in result["messages"][-1].text
    assert not (tmp_path / "missing.db").exists()


async def test_clinical_question_gets_the_fixed_decline(db_env: Path) -> None:
    graph = build_graph(no_agent(), classifier("clinical"))
    result = await ask(graph, "Should he take an extra dose?", Context())
    assert result["route"] == "clinical"
    assert result["messages"][-1].text == CLINICAL_RESPONSE


def test_callers_can_only_send_messages() -> None:
    graph = build_graph(no_agent(), classifier("normal"))
    assert set(graph.get_input_jsonschema()["properties"]) == {"messages"}
    assert {"route", "incident_id"} <= set(graph.get_output_jsonschema()["properties"])


async def test_route_sent_by_caller_is_ignored(db_env: Path) -> None:
    graph = build_graph(no_agent(), classifier("clinical"))
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


async def test_normal_question_reaches_the_agent(db_env: Path) -> None:
    agent = AnsweringModel(messages=iter([AIMessage(content="Here is the schedule.")]))
    graph = build_graph(agent, classifier("normal"))
    result = await ask(graph, "What's on today?", Context())
    assert result["route"] == "normal"
    assert result["messages"][-1].text == "Here is the schedule."
