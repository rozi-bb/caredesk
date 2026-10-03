"""Triage: decide whether a message is an emergency, a clinical question, or normal.

Runs before anything else (ADR-0006). Unmistakable emergencies are caught by
a keyword check that needs no model call (ADR-0016). Everything else is
classified by the model; if that call fails, the message is treated as an
emergency, because a false alarm is cheap and a missed emergency is not.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from agent.context import Context
from agent.db import REFERENCE_DATE, connect_writable

Route = Literal["emergency", "clinical", "normal"]

_EMERGENCY_PHRASES = [
    r"not breathing",
    r"(can't|cannot|can not|struggling to) breathe",
    r"stopped breathing",
    r"chest pains?",
    r"unconscious",
    r"unresponsive",
    r"(isn't|is not|won't|will not|not) waking up",
    r"can't wake",
    r"choking",
    r"bleeding (heavily|a lot|badly)",
    r"(i|i've|i have|has|have) (just )?(fallen|fell)( down)?\b(?! (last|yesterday|on|in|two|three|a few|earlier))",
    r"just (fell|fallen)",
    r"on the floor and can't get up",
    r"can't get up",
    r"(there's|there is) (a )?fire",
    r"on fire",
    r"(smell|see|there's|there is) smoke",
    r"smoke (is )?(coming|in)",
]
EMERGENCY_KEYWORDS = re.compile(
    r"\b(" + "|".join(_EMERGENCY_PHRASES) + r")", re.IGNORECASE
)

TRIAGE_PROMPT = """\
Classify the user's latest message to a nursing home's administrative assistant.

emergency: someone may be in danger right now. For example a fall that is happening or
just happened, trouble breathing, chest pain, someone unresponsive, sudden confusion or
a drooping face, choking, heavy bleeding, fire or smoke, a resident missing, or someone
being hurt.

clinical: asks for medical judgement. For example diagnosis, what a symptom or test
result means, whether to take, stop, or change a medicine or its dose, or what treatment
someone should have.

normal: everything else. This includes administrative questions about schedules,
medication-round times, visits, billing, past incidents (for example "was last week's
fall recorded?"), and what the rules say about restraints, bed rails, or refusing care.

When a message could be an emergency, choose emergency.

Reply with JSON only:
{"category": "emergency" | "clinical" | "normal", "reason": "<one short sentence>"}"""

EMERGENCY_RESPONSE = """\
This sounds like an emergency. If someone is in danger right now:
- Press the call bell or alert the nearest staff member.
- Call the nurse station on extension 200 (staffed 24 hours).
- If someone's life is in danger, call 911.

{recorded}
I am an administrative assistant and cannot assess the situation myself."""

RECORDED = "I have recorded your message for the nursing team to follow up."
NOT_RECORDED = (
    "I could not record your message, so please also tell a staff member directly."
)

CLINICAL_RESPONSE = """\
I can't give medical advice, diagnoses, or guidance about medication or treatment.
Please speak to the nursing staff at the nurse station (extension 200, staffed 24 hours),
who can look at the situation properly.
If you think someone is in danger right now, press the call bell or call 911."""


class TriageResult(BaseModel):
    """The model's classification of one message."""

    category: Route = Field(description="emergency, clinical, or normal")
    reason: str = Field(description="One short sentence explaining the choice")


def keyword_emergency(text: str) -> bool:
    """Return True for phrases that are emergencies without any interpretation."""
    return EMERGENCY_KEYWORDS.search(text) is not None


def record_emergency(ctx: Context, message: str) -> int | None:
    """Write a 'needs action' incident for an emergency message.

    Returns the incident id, or None if it could not be written. A failure here
    must never stop the emergency response from reaching the user.
    """
    try:
        conn = connect_writable()
    except (FileNotFoundError, sqlite3.Error):
        return None
    try:
        resident: int | None = None
        reporter: int | None = None
        if ctx.role == "family":
            linked = conn.execute(
                "SELECT resident_id FROM family_links WHERE family_member_id = ?",
                (ctx.user_id,),
            ).fetchall()
            if len(linked) == 1:
                resident = linked[0][0]
        elif ctx.role == "staff":
            known = conn.execute(
                "SELECT 1 FROM staff WHERE id = ?", (ctx.user_id,)
            ).fetchone()
            reporter = ctx.user_id if known else None
        when = f"{REFERENCE_DATE.isoformat()}T{datetime.now():%H:%M}"
        text = f'Automatic record: emergency message from {ctx.role} #{ctx.user_id}: "{message[:500]}"'
        cursor = conn.execute(
            "INSERT INTO incidents (resident_id, reported_by_staff_id, occurred_at, "
            "category, description, status) VALUES (?, ?, ?, 'emergency', ?, 'needs_action')",
            (resident, reporter, when, text),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error:
        return None
    finally:
        conn.close()
