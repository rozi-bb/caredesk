"""Shared machinery: a fresh database, the target function, and suite runs."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langsmith import Client

ROOT = Path(__file__).resolve().parent.parent

Example = dict[str, dict[str, Any]]
Evaluator = Callable[..., dict[str, Any]]


@dataclass
class Suite:
    """One evaluation suite: a versioned dataset and the checks applied to it."""

    name: str
    dataset: str
    description: str
    build_examples: Callable[[sqlite3.Connection], list[Example]]
    evaluators: list[Evaluator]
    required: frozenset[str] = frozenset()  # checks that must pass on every example
    results: dict[str, list[bool]] = field(default_factory=dict)


def fresh_database() -> Path:
    """Seed a throwaway copy of the database and point the app at it.

    Evaluations can write incident records, so they never touch data/caredesk.db.
    """
    path = Path(tempfile.mkdtemp(prefix="caredesk-eval-")) / "caredesk.db"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_db.py"), "--output", str(path)],
        check=True,
        capture_output=True,
    )
    os.environ["CAREDESK_DB_PATH"] = str(path)
    return path


def user_id(conn: sqlite3.Connection, role: str, name: str) -> int:
    """Look up a user's id by role and full name; 0 when unknown."""
    table = {"staff": "staff", "family": "family_members"}.get(role)
    if table is None:
        return 0
    row = conn.execute(
        f"SELECT id FROM {table} WHERE full_name = ?", (name,)
    ).fetchone()
    return int(row[0]) if row else 0


def make_target(db: Path) -> Callable[[dict[str, Any]], Any]:
    """Return the function LangSmith calls once per example."""
    from agent.context import Context
    from agent.graph import build_graph

    graph = build_graph()

    async def target(inputs: dict[str, Any]) -> dict[str, Any]:
        with sqlite3.connect(db) as conn:
            uid = user_id(conn, inputs["role"], inputs.get("user_name", ""))
        role = inputs["role"] if uid else "unknown"
        result = await graph.ainvoke(
            {"messages": [HumanMessage(inputs["question"])]},
            context=Context(user_id=uid, role=role),
        )
        messages = result["messages"]
        return {
            "answer": messages[-1].text,
            "route": result.get("route", "normal"),
            "incident_id": result.get("incident_id"),
            "tool_calls": [
                call["name"]
                for m in messages
                if isinstance(m, AIMessage)
                for call in m.tool_calls
            ],
            "tool_outputs": [m.text for m in messages if isinstance(m, ToolMessage)],
        }

    return target


def git_revision() -> str:
    """Return the short commit hash, so each experiment is tied to code."""
    out = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return out.stdout.strip() or "unknown"


async def run_suite(client: Client, suite: Suite, db: Path) -> bool:
    """Create the dataset if needed, run the experiment, and report results."""
    if not client.has_dataset(dataset_name=suite.dataset):
        with sqlite3.connect(db) as conn:
            examples = suite.build_examples(conn)
        dataset = client.create_dataset(suite.dataset, description=suite.description)
        client.create_examples(dataset_id=dataset.id, examples=examples)
        print(f"Created dataset {suite.dataset} with {len(examples)} examples")

    from agent.graph import MODEL_NAME

    results = await client.aevaluate(
        make_target(db),
        data=suite.dataset,
        evaluators=suite.evaluators,
        experiment_prefix=suite.name,
        metadata={"model": MODEL_NAME, "git": git_revision()},
        max_concurrency=4,
    )
    failures: list[str] = []
    async for row in results:
        question = row["example"].inputs["question"]
        for result in row["evaluation_results"]["results"]:
            if result.score is None:  # check does not apply to this example
                continue
            suite.results.setdefault(result.key, []).append(bool(result.score))
            if not result.score:
                failures.append(f"  [{result.key}] {question}\n      {result.comment}")

    print(f"\n== {suite.name}  ({results.experiment_name})")
    passed = True
    for key, scores in suite.results.items():
        rate = sum(scores) / len(scores)
        required = key in suite.required
        print(
            f"  {key:<28}{sum(scores):>3}/{len(scores):<3} {rate:6.0%}{'  (required 100%)' if required else ''}"
        )
        passed = passed and (rate == 1.0 or not required)
    if failures:
        print("  failures:")
        print("\n".join(failures))
    if suite.required:
        print(f"  required checks: {'PASS' if passed else 'FAIL'}")
    return passed
