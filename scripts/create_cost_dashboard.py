"""Create the "CareDesk cost" dashboard in LangSmith (ADR-0033).

Charts the cost LangSmith computes from traces in the tracing project: totals
for chat requests from the backend at the top, then bar charts split by the
metadata the backend attaches to every request (account, role, and channel).
Without --replace it runs once: if the dashboard exists, nothing is changed.

Needs LANGSMITH_API_KEY; reads LANGSMITH_PROJECT (default caredesk) and
LANGSMITH_ENDPOINT. Makes real calls to the LangSmith API, never to a model.

Usage:
    uv run --env-file .env python scripts/create_cost_dashboard.py [--replace]
"""

from __future__ import annotations

import argparse
import os
from typing import Any

import httpx
from langsmith import Client

TITLE = "CareDesk cost"
DESCRIPTION = (
    "Cost from LangSmith's own price table, per chat request (root trace). "
    "Compare with scripts/cost_report.py, which prices every input token as a "
    "cache miss and adds Jev."
)

ROOT = "eq(is_root, true)"
# Only the backend sets `account_id`; Studio runs have none. Not `channel`:
# requests from before the Telegram release were traced without it.
BACKEND = 'and(eq(is_root, true), eq(metadata_key, "account_id"))'

TOTAL_COST = {"type": "sum", "field": "total_cost"}
AVERAGE_COST = {"type": "avg", "field": "total_cost"}
REQUESTS = {"type": "count"}

# (chart title, chart type, what to measure, which runs, metadata key to split by)
CHARTS: list[tuple[str, str, dict[str, str], str, str | None]] = [
    ("Total cost ($)", "kpi", TOTAL_COST, BACKEND, None),
    ("Requests", "kpi", REQUESTS, BACKEND, None),
    ("Average cost per request ($)", "kpi", AVERAGE_COST, BACKEND, None),
    ("Cost per account ($)", "bar", TOTAL_COST, ROOT, "account_id"),
    ("Requests per account", "bar", REQUESTS, ROOT, "account_id"),
    ("Cost per role ($)", "bar", TOTAL_COST, ROOT, "role"),
    ("Cost per channel ($)", "bar", TOTAL_COST, ROOT, "channel"),
]


def chart(
    title: str,
    chart_type: str,
    metric: dict[str, str],
    run_filter: str,
    key: str | None,
    project_id: str,
    section_id: str,
    index: int,
) -> dict[str, Any]:
    """Request body for one chart of root traces, split by a metadata key if given.

    A root trace is one chat request, and its cost includes every model call in it.
    """
    series: dict[str, Any] = {
        "name": title,
        "metric_definition": metric,
        "filter_definition": {
            "source_type": "tracing_project",
            "project_ids": [project_id],
            "run_filter": run_filter,
        },
    }
    if key:
        series["group_by_definitions"] = [{"attribute": "metadata", "path": key}]
    return {
        "title": title,
        "chart_type": chart_type,
        "section_id": section_id,
        "index": index,
        "series": [series],
    }


def main() -> None:
    """Create the section and its charts, replacing an existing one if asked."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--replace", action="store_true", help="delete the dashboard and build it again"
    )
    args = parser.parse_args()

    project = Client().read_project(
        project_name=os.environ.get("LANGSMITH_PROJECT", "caredesk")
    )
    base = os.environ.get(
        "LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"
    ).rstrip("/")
    with httpx.Client(
        base_url=f"{base}/api/v1",
        headers={"x-api-key": os.environ["LANGSMITH_API_KEY"]},
        timeout=30,
    ) as api:
        sections = api.get("/charts/section").raise_for_status().json()
        existing = [section for section in sections if section["title"] == TITLE]
        if existing and not args.replace:
            print(
                f'"{TITLE}" already exists; nothing changed. Use --replace to rebuild.'
            )
            return
        for section in existing:
            api.delete(f"/charts/section/{section['id']}").raise_for_status()
            print(f'Deleted the old "{TITLE}" dashboard.')
        section = (
            api.post(
                "/charts/section", json={"title": TITLE, "description": DESCRIPTION}
            )
            .raise_for_status()
            .json()
        )
        try:
            for index, spec in enumerate(CHARTS):
                body = chart(*spec, str(project.id), section["id"], index)
                api.post("/charts/create", json=body).raise_for_status()
                print(f"Created chart: {spec[0]}")
        except httpx.HTTPStatusError:
            # A half-built dashboard would make the next run think it is done.
            api.delete(f"/charts/section/{section['id']}")
            raise
    print(f'Dashboard "{TITLE}" is under Monitoring > Dashboards in LangSmith.')


if __name__ == "__main__":
    main()
