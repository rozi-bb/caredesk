"""Triage: decide whether a message is an emergency, a clinical question, or normal.

Runs before anything else (ADR-0006). Jev labels every message; if Jev fails,
the DeepSeek classifier labels it instead; if both fail, the message cannot
be checked and gets a fixed reply with the emergency contacts (ADR-0029).
Every reply here is fixed text, and nothing is written to the database
(ADR-0030).
"""

from __future__ import annotations

import asyncio
from functools import cache
from typing import Literal, get_args

from langsmith import traceable
from pydantic import BaseModel, Field
from typesafe_sdk import AsyncTypeSafeClient, Choice, RetryPolicy

Route = Literal["emergency", "clinical", "normal"]
# "unavailable" is never a classifier's answer: it means no classifier answered.
TriageRoute = Literal["emergency", "clinical", "normal", "unavailable"]

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

# The home's emergency contacts, written once. Every fixed text below, and the
# notice the chat UI and the Telegram bot show (served by the backend), uses them.
NURSE_STATION = "extension 200"
EMERGENCY_NUMBER = "911"
EMERGENCY_NOTICE = (
    f"In an emergency, press the call bell, call the nurse station on {NURSE_STATION}, "
    f"or call {EMERGENCY_NUMBER}."
)

EMERGENCY_RESPONSE = f"""\
This sounds like an emergency. If someone is in danger right now:
- Press the call bell or alert the nearest staff member.
- Call the nurse station on {NURSE_STATION} (staffed 24 hours).
- If someone's life is in danger, call {EMERGENCY_NUMBER}.

I am an administrative assistant and cannot assess the situation myself."""

CLINICAL_RESPONSE = f"""\
I can't give medical advice, diagnoses, or guidance about medication or treatment.
Please speak to the nursing staff at the nurse station ({NURSE_STATION}, staffed 24 hours),
who can look at the situation properly.
If you think someone is in danger right now, press the call bell or call {EMERGENCY_NUMBER}."""

UNAVAILABLE_RESPONSE = f"""\
I can't check your message right now because part of our system is unavailable.
If someone is in danger, press the call bell, call the nurse station on {NURSE_STATION} (staffed 24 hours), or call {EMERGENCY_NUMBER}.
For anything else, please try again in a few minutes."""


class TriageResult(BaseModel):
    """The model's classification of one message."""

    category: Route = Field(description="emergency, clinical, or normal")
    reason: str = Field(description="One short sentence explaining the choice")


JEV_MODEL = "jev-latest"
# Jev's 95th percentile was 0.7 s in the J3 comparison; a hung call is cut
# short so the fallback still answers quickly.
JEV_TIMEOUT = 3.0
# Chosen in J3: below every ordinary look-alike (at most 0.25), so emergencies
# that Jev ranks second, such as suspected abuse, still count (ADR-0029).
EMERGENCY_THRESHOLD = 0.3

JEV_QUESTION = Choice(
    instructions=(
        "Classify the user's latest message to a nursing home's administrative "
        "assistant. When a message could be an emergency, choose emergency."
    ),
    criteria={
        "emergency": {
            "what": "Someone may be in danger right now: a fall that is happening or "
            "just happened, trouble breathing, chest pain, someone unresponsive, "
            "sudden confusion or a drooping face, choking, heavy bleeding, fire or "
            "smoke, a resident missing, or someone being hurt, hit, or treated "
            "roughly by another person, including suspected abuse.",
            "not_for": "General questions about what a policy, procedure, or rule "
            "says, such as what staff do when a resident chokes or what the fire "
            "evacuation procedure is; questions about past events, such as whether "
            "last week's fall was recorded; and appointments.",
        },
        "clinical": {
            "what": "Asks for medical judgement: a diagnosis, what a symptom or test "
            "result means, whether to take, stop, or change a medicine or its dose, "
            "or what treatment someone should have.",
            "not_for": "Medication-round times or other schedules.",
        },
        "normal": {
            "what": "Everything else, including administrative questions about "
            "schedules, medication-round times, visits, billing, past incidents, "
            "and what the rules say about restraints, bed rails, or refusing care.",
        },
    },
)


@cache
def _jev_client(loop: asyncio.AbstractEventLoop) -> AsyncTypeSafeClient:
    # One client per event loop: its connection pool belongs to the loop that
    # created it, and reusing a warm connection is what keeps Jev fast.
    return AsyncTypeSafeClient(
        model=JEV_MODEL, retry=RetryPolicy(max_retries=0), timeout=JEV_TIMEOUT
    )


@traceable(name="jev_triage")
async def jev_probabilities(text: str) -> dict[str, float]:
    """Ask Jev how likely the message is to be each triage label.

    No retries (ADR-0029): a retry would double the wait, and an unclear
    outcome could be billed twice. Any failure raises, so the caller can fall
    back to the other classifier.
    """
    async with asyncio.timeout(JEV_TIMEOUT):
        response = await _jev_client(asyncio.get_running_loop()).system_one(
            state=text, questions={"triage": JEV_QUESTION}
        )
    return dict(response.choices["triage"].probabilities)


def jev_route(probabilities: dict[str, float]) -> Route:
    """Turn Jev's probabilities into a route, leaning toward emergency.

    Raises ValueError if the labels are not exactly the triage labels, so an
    unexpected answer is handled like any other Jev failure.
    """
    labels: tuple[Route, ...] = get_args(Route)
    if set(probabilities) != set(labels):
        raise ValueError(f"Unexpected Jev labels: {sorted(probabilities)}")
    if probabilities["emergency"] >= EMERGENCY_THRESHOLD:
        return "emergency"
    return max(labels, key=lambda label: probabilities[label])
