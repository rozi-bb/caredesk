"""Tools the model can call. Read-only.

The caller's identity comes from the injected `runtime`, which the model
cannot see or set. All permission checks live in `agent.records`.
"""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import ToolRuntime

from agent import records
from agent.context import Context
from agent.db import connect_readonly


def _with_db(
    query: Callable[..., str], *args: str, runtime: ToolRuntime[Context]
) -> str:
    conn = connect_readonly()
    try:
        return query(conn, runtime.context or Context(), *args)
    finally:
        conn.close()


@tool
def get_my_profile(*, runtime: ToolRuntime[Context]) -> str:
    """Return who the current user is and, for family, which residents they are linked to."""
    return _with_db(records.my_profile, runtime=runtime)


@tool
def get_resident(resident: str = "", *, runtime: ToolRuntime[Context]) -> str:
    """Return a resident's room, care level, and when they moved in.

    Args:
        resident: Resident's name. Leave empty if the user means their own linked resident.
    """
    return _with_db(records.resident_info, resident, runtime=runtime)


@tool
def get_schedule(
    resident: str = "", day: str = "", *, runtime: ToolRuntime[Context]
) -> str:
    """Return one resident's care schedule for one day.

    Args:
        resident: Resident's name. Leave empty if the user means their own linked resident.
        day: 'today', 'tomorrow', 'yesterday', or YYYY-MM-DD. Empty means today.
    """
    return _with_db(records.schedule, resident, day, runtime=runtime)


@tool
def get_activities(day: str = "", *, runtime: ToolRuntime[Context]) -> str:
    """Return the shared activities (group events) for one day.

    Args:
        day: 'today', 'tomorrow', 'yesterday', or YYYY-MM-DD. Empty means today.
    """
    return _with_db(records.activities, day, runtime=runtime)


@tool
def get_visits(
    resident: str = "", start: str = "", end: str = "", *, runtime: ToolRuntime[Context]
) -> str:
    """Return family visits for one resident between two days, inclusive.

    Args:
        resident: Resident's name. Leave empty if the user means their own linked resident.
        start: First day. 'today', 'tomorrow', 'yesterday', or YYYY-MM-DD. Empty means today.
        end: Last day, same format. Empty means the same as start.
    """
    return _with_db(records.visits, resident, start, end, runtime=runtime)


@tool
def get_incidents(
    status: str = "needs_action", *, runtime: ToolRuntime[Context]
) -> str:
    """Return incident records (falls, complaints, missing belongings). Staff only.

    Args:
        status: 'needs_action', 'resolved', or 'all'.
    """
    return _with_db(records.incidents, status, runtime=runtime)


@tool
def get_billing(resident: str = "", *, runtime: ToolRuntime[Context]) -> str:
    """Return a resident's monthly invoices and whether they are paid.

    Args:
        resident: Resident's name. Leave empty if the user means their own linked resident.
    """
    return _with_db(records.billing, resident, runtime=runtime)


RECORD_TOOLS: list[BaseTool] = [
    get_my_profile,
    get_resident,
    get_schedule,
    get_activities,
    get_visits,
    get_incidents,
    get_billing,
]
