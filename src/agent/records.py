"""Read access to the home's records, filtered by who is asking.

Every function takes the caller's identity and applies the permission rules
of docs/prd.md section 3 inside its own query (ADR-0002). A resident outside
the caller's scope gets the same reply as one that does not exist, so the
assistant cannot be used to probe who lives here (ADR-0013).
"""

from __future__ import annotations

import difflib
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from agent.context import Context
from agent.db import REFERENCE_DATE

NO_IDENTITY = "No user identity was provided, so no records can be shown."
STAFF_ONLY = "Only staff can see incident records."
_TITLES = {"mr", "mrs", "ms", "miss", "dr", "mister", "missus"}


@dataclass(frozen=True)
class ResidentRef:
    """A resident the caller is allowed to see."""

    id: int
    full_name: str
    room: str


def _normalize(name: str) -> str:
    words = re.sub(r"[^a-z\s]", " ", name.lower()).split()
    return " ".join(w for w in words if w not in _TITLES)


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _known(conn: sqlite3.Connection, ctx: Context) -> bool:
    table = {"staff": "staff", "family": "family_members"}.get(ctx.role)
    if table is None:
        return False
    row = conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (ctx.user_id,)).fetchone()
    return row is not None


def visible_residents(conn: sqlite3.Connection, ctx: Context) -> list[ResidentRef]:
    """Return the residents whose records the caller may see."""
    if not _known(conn, ctx):
        return []
    if ctx.role == "staff":
        rows = conn.execute(
            "SELECT id, full_name, room FROM residents ORDER BY full_name"
        )
    else:
        rows = conn.execute(
            "SELECT r.id, r.full_name, r.room FROM residents r "
            "JOIN family_links l ON l.resident_id = r.id "
            "WHERE l.family_member_id = ? ORDER BY r.full_name",
            (ctx.user_id,),
        )
    return [ResidentRef(r["id"], r["full_name"], r["room"]) for r in rows]


def resolve_resident(
    conn: sqlite3.Connection, ctx: Context, query: str
) -> ResidentRef | str:
    """Find one visible resident by name, or explain why not.

    An empty name means "my resident" and works when the caller sees exactly
    one. Ambiguous names are never guessed: the caller is asked to choose.
    """
    candidates = visible_residents(conn, ctx)
    if not candidates:
        return (
            NO_IDENTITY
            if not _known(conn, ctx)
            else "You are not linked to any resident."
        )
    wanted = _normalize(query)
    if not wanted:
        if len(candidates) == 1:
            return candidates[0]
        names = ", ".join(c.full_name for c in candidates)
        return f"Please say which resident you mean: {names}."

    exact = [c for c in candidates if _normalize(c.full_name) == wanted]
    if len(exact) == 1:
        return exact[0]
    words = set(wanted.split())
    partial = [c for c in candidates if words <= set(_normalize(c.full_name).split())]
    if len(partial) == 1:
        return partial[0]
    if partial:
        options = "; ".join(f"{c.full_name} (room {c.room})" for c in partial)
        return f"Several residents match '{query}': {options}. Which one do you mean?"

    not_found = f"No resident you have access to matches '{query}'."
    by_key = {_normalize(c.full_name): c.full_name for c in candidates}
    close = difflib.get_close_matches(wanted, list(by_key), n=3, cutoff=0.8)
    if close:
        return f"{not_found} Did you mean: {', '.join(by_key[c] for c in close)}?"
    return not_found


def parse_day(text: str) -> date | str:
    """Turn '', 'today', 'tomorrow', 'yesterday', or YYYY-MM-DD into a date."""
    word = text.strip().lower()
    relative = {"": 0, "today": 0, "tomorrow": 1, "yesterday": -1}
    if word in relative:
        return REFERENCE_DATE + timedelta(days=relative[word])
    try:
        return date.fromisoformat(word)
    except ValueError:
        return f"Could not read the date '{text}'. Use YYYY-MM-DD."


def my_profile(conn: sqlite3.Connection, ctx: Context) -> str:
    """Describe the caller and, for family, the residents they are linked to."""
    if not _known(conn, ctx):
        return NO_IDENTITY
    if ctx.role == "staff":
        row = conn.execute(
            "SELECT full_name, job_title FROM staff WHERE id = ?", (ctx.user_id,)
        ).fetchone()
        return f"You are {row['full_name']}, staff ({row['job_title']}). You can see all residents."
    me = conn.execute(
        "SELECT full_name FROM family_members WHERE id = ?", (ctx.user_id,)
    ).fetchone()
    links = conn.execute(
        "SELECT r.full_name, r.room, l.relationship, l.can_view_billing "
        "FROM family_links l JOIN residents r ON r.id = l.resident_id "
        "WHERE l.family_member_id = ? ORDER BY r.full_name",
        (ctx.user_id,),
    ).fetchall()
    lines = [f"You are {me['full_name']}, a family member. Linked residents:"]
    for link in links:
        billing = (
            "can see billing" if link["can_view_billing"] else "cannot see billing"
        )
        relationship = link["relationship"].replace("_", "/")
        lines.append(
            f"- {link['full_name']} (room {link['room']}), you are their {relationship}; {billing}"
        )
    return "\n".join(lines)


def resident_info(conn: sqlite3.Connection, ctx: Context, resident: str) -> str:
    """Return a resident's room, care level, and admission date."""
    who = resolve_resident(conn, ctx, resident)
    if isinstance(who, str):
        return who
    row = conn.execute(
        "SELECT care_level, admitted_on FROM residents WHERE id = ?", (who.id,)
    ).fetchone()
    level = row["care_level"].replace("_", " ")
    return (
        f"{who.full_name}: room {who.room}, care level {level}, "
        f"living here since {row['admitted_on']}."
    )


def schedule(conn: sqlite3.Connection, ctx: Context, resident: str, day: str) -> str:
    """List one resident's care schedule for one day."""
    who = resolve_resident(conn, ctx, resident)
    if isinstance(who, str):
        return who
    when = parse_day(day)
    if isinstance(when, str):
        return when
    rows = conn.execute(
        "SELECT substr(scheduled_for, 12, 5) AS hhmm, description FROM schedule_items "
        "WHERE resident_id = ? AND scheduled_for LIKE ? ORDER BY scheduled_for",
        (who.id, f"{when.isoformat()}%"),
    ).fetchall()
    if not rows:
        return f"{who.full_name} has nothing scheduled on {when:%A %d %B %Y}."
    lines = [f"Schedule for {who.full_name} (room {who.room}) on {when:%A %d %B %Y}:"]
    lines += [f"- {r['hhmm']} {r['description']}" for r in rows]
    return "\n".join(lines)


def activities(conn: sqlite3.Connection, ctx: Context, day: str) -> str:
    """List the shared activities for one day. Any known user may see these."""
    if not _known(conn, ctx):
        return NO_IDENTITY
    when = parse_day(day)
    if isinstance(when, str):
        return when
    rows = conn.execute(
        "SELECT substr(starts_at, 12, 5) AS hhmm, title, location, duration_minutes "
        "FROM activities WHERE starts_at LIKE ? ORDER BY starts_at",
        (f"{when.isoformat()}%",),
    ).fetchall()
    if not rows:
        return f"No activities are planned on {when:%A %d %B %Y}."
    lines = [f"Activities on {when:%A %d %B %Y}:"]
    lines += [
        f"- {r['hhmm']} {r['title']} ({r['location']}, {r['duration_minutes']} min)"
        for r in rows
    ]
    return "\n".join(lines)


def visits(
    conn: sqlite3.Connection, ctx: Context, resident: str, start: str, end: str
) -> str:
    """List family visits for one resident between two days (inclusive)."""
    who = resolve_resident(conn, ctx, resident)
    if isinstance(who, str):
        return who
    first = parse_day(start or "today")
    last = parse_day(end) if end else first
    if isinstance(first, str):
        return first
    if isinstance(last, str):
        return last
    rows = conn.execute(
        "SELECT v.scheduled_for, v.status, f.full_name FROM visits v "
        "JOIN family_members f ON f.id = v.family_member_id "
        "WHERE v.resident_id = ? AND substr(v.scheduled_for, 1, 10) BETWEEN ? AND ? "
        "ORDER BY v.scheduled_for",
        (who.id, first.isoformat(), last.isoformat()),
    ).fetchall()
    span = f"{first:%d %B}" if first == last else f"{first:%d %B} to {last:%d %B %Y}"
    if not rows:
        return f"No visits for {who.full_name} on {span}."
    lines = [f"Visits for {who.full_name}, {span}:"]
    lines += [
        f"- {r['scheduled_for'].replace('T', ' ')} {r['full_name']}: {r['status']}"
        for r in rows
    ]
    return "\n".join(lines)


def incidents(conn: sqlite3.Connection, ctx: Context, status: str) -> str:
    """List incident records. Staff only."""
    if not _known(conn, ctx):
        return NO_IDENTITY
    if ctx.role != "staff":
        return STAFF_ONLY
    wanted = status.strip().lower() or "needs_action"
    if wanted not in {"needs_action", "resolved", "all"}:
        return "Status must be 'needs_action', 'resolved', or 'all'."
    where = "" if wanted == "all" else "WHERE i.status = ?"
    params: tuple[str, ...] = () if wanted == "all" else (wanted,)
    rows = conn.execute(
        "SELECT i.occurred_at, i.category, i.description, i.status, r.full_name "
        "FROM incidents i LEFT JOIN residents r ON r.id = i.resident_id "
        f"{where} ORDER BY i.occurred_at DESC",
        params,
    ).fetchall()
    if not rows:
        return f"No incidents with status '{wanted}'."
    lines = [f"Incidents ({wanted}):"]
    for r in rows:
        resident = r["full_name"] or "resident unknown"
        lines.append(
            f"- {r['occurred_at'].replace('T', ' ')} {resident}: {r['category']}, "
            f"{r['status']}. {r['description']}"
        )
    return "\n".join(lines)


def billing(conn: sqlite3.Connection, ctx: Context, resident: str) -> str:
    """List a resident's invoices, if the caller may see them."""
    who = resolve_resident(conn, ctx, resident)
    if isinstance(who, str):
        return who
    if ctx.role == "family":
        allowed = conn.execute(
            "SELECT can_view_billing FROM family_links "
            "WHERE resident_id = ? AND family_member_id = ?",
            (who.id, ctx.user_id),
        ).fetchone()
        if not allowed or not allowed["can_view_billing"]:
            return f"You do not have permission to see billing for {who.full_name}."
    rows = conn.execute(
        "SELECT period, amount_cents, status FROM billing WHERE resident_id = ? ORDER BY period",
        (who.id,),
    ).fetchall()
    lines = [f"Invoices for {who.full_name}:"]
    lines += [
        f"- {r['period']}: {_money(r['amount_cents'])}, {r['status']}" for r in rows
    ]
    return "\n".join(lines)
