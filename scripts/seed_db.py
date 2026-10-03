"""Generate the synthetic Evergreen Care Home database.

Everything comes from one fixed seed, so running this twice produces the
same data (with the Faker version pinned in uv.lock). All people are
fictional and every phone number is in the reserved fictional 555-01xx range.

Usage:
    uv run python scripts/seed_db.py [--output PATH]
"""

from __future__ import annotations

import argparse
import random
import re
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import NamedTuple

from faker import Faker

from agent.db import REFERENCE_DATE, SCHEMA_PATH

SEED = 42
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "caredesk.db"

NUM_RESIDENTS = 30
DAYS_BEFORE = 7
DAYS_AFTER = 6

TABLES = (
    "residents",
    "staff",
    "family_members",
    "family_links",
    "schedule_items",
    "activities",
    "visits",
    "incidents",
    "billing",
)

# Hard cases planted on purpose, to test the assistant (see docs/prd.md section 7).
PLANTED_RESIDENTS = (
    ("Mary Johnson", "assisted"),  # near-identical name ...
    ("Marie Johnson", "assisted"),  # ... to this one
    ("Harold Bennett", "assisted"),  # four children, only one may see billing
    ("Dorothy Hale", "independent"),  # no family registered
    ("Rosa Moreno", "memory_care"),  # linked to Linda Moreno
    ("Hector Alvarez", "independent"),  # also linked to Linda Moreno, other access
    ("Edith Carter", "assisted"),  # double-booked slot
)
PLANTED_STAFF = (("Karen Mitchell", "nurse"),)  # shares a name with a family member
# (resident, family member, relationship, may see billing)
PLANTED_LINKS = (
    ("Harold Bennett", "Peter Bennett", "son", True),
    ("Harold Bennett", "Anne Bennett", "daughter", False),
    ("Harold Bennett", "Paul Bennett", "son", False),
    ("Harold Bennett", "Claire Whitman", "daughter", False),
    ("Rosa Moreno", "Linda Moreno", "daughter", True),
    ("Hector Alvarez", "Linda Moreno", "niece_nephew", False),
    ("Mary Johnson", "Karen Mitchell", "daughter", True),
    ("Marie Johnson", "Tom Johnson", "son", True),
    ("Edith Carter", "George Carter", "son", True),
)

STAFF_TITLES = (
    ["nurse"] * 4  # plus the planted nurse
    + ["caregiver"] * 6
    + ["physiotherapist", "activities_coordinator", "administrator", "manager"]
)
RELATIONSHIPS = ("daughter", "son", "spouse", "grandchild", "niece_nephew", "friend")
RELATIONSHIP_WEIGHTS = (30, 28, 10, 15, 12, 5)
MONTHLY_FEE_CENTS = {
    "independent": 380_000,
    "assisted": 560_000,
    "memory_care": 740_000,
}

ACTIVITY_TEMPLATES = (
    ("Morning stretching", "Lounge", 45),
    ("Bingo", "Dining room", 60),
    ("Music hour", "Lounge", 60),
    ("Garden walk", "Garden", 45),
    ("Chair yoga", "Lounge", 45),
    ("Movie afternoon", "Dining room", 90),
    ("Arts and crafts", "Activity room", 60),
)
APPOINTMENTS = (
    "Visiting doctor appointment",
    "Hairdresser",
    "Podiatrist visit",
    "Optician visit",
)
INCIDENT_TEXT = {
    "fall": "Resident slipped in the corridor. Staff assisted and a nurse was informed.",
    "missing_belongings": "Family reported a missing item of personal belongings.",
    "complaint": "Family raised a complaint about a slow response to the call bell.",
    "behaviour": "Resident was upset during the evening meal. A caregiver stayed with them.",
    "emergency": "Automatic record: an emergency message was received.",
}


class Resident(NamedTuple):
    """A resident of the home."""

    id: int
    full_name: str
    room: str
    care_level: str
    admitted_on: str


class Staff(NamedTuple):
    """A staff member."""

    id: int
    full_name: str
    job_title: str


def _moment(day: date, hour: int, minute: int = 0) -> str:
    return datetime.combine(day, time(hour, minute)).isoformat(timespec="minutes")


def _unique_name(
    fake: Faker, rng: random.Random, used: set[str], last_name: str | None = None
) -> str:
    while True:
        first = (
            fake.first_name_female() if rng.random() < 0.5 else fake.first_name_male()
        )
        name = f"{first} {last_name or fake.last_name()}"
        if name not in used:
            used.add(name)
            return name


def _contact(rng: random.Random, name: str) -> tuple[str, str]:
    slug = re.sub(r"[^a-z.]", "", name.lower().replace(" ", "."))
    return f"555-01{rng.randint(0, 99):02d}", f"{slug}@example.org"


def make_residents(fake: Faker, rng: random.Random) -> list[Resident]:
    """Build the 30 residents, planted ones first."""
    used = {name for name, _ in PLANTED_RESIDENTS}
    generated = NUM_RESIDENTS - len(PLANTED_RESIDENTS)
    levels = ["independent"] * 8 + ["assisted"] * 10 + ["memory_care"] * 5
    assert len(levels) == generated
    rng.shuffle(levels)
    people = list(PLANTED_RESIDENTS) + [
        (_unique_name(fake, rng, used), level) for level in levels
    ]
    rooms = [f"{floor}{number:02d}" for floor in (1, 2) for number in range(1, 16)]
    rng.shuffle(rooms)
    return [
        Resident(
            id=index,
            full_name=name,
            room=rooms[index - 1],
            care_level=level,
            admitted_on=(
                REFERENCE_DATE - timedelta(days=rng.randint(30, 3000))
            ).isoformat(),
        )
        for index, (name, level) in enumerate(people, start=1)
    ]


def make_staff(fake: Faker, rng: random.Random) -> list[Staff]:
    """Build the 15 staff members, planted ones first."""
    used = {name for name, _ in PLANTED_STAFF}
    people = list(PLANTED_STAFF) + [
        (_unique_name(fake, rng, used), title) for title in STAFF_TITLES
    ]
    return [
        Staff(index, name, title) for index, (name, title) in enumerate(people, start=1)
    ]


def make_family(
    fake: Faker, rng: random.Random, residents: list[Resident]
) -> tuple[list[tuple[int, str, str, str]], list[tuple[int, int, str, int]]]:
    """Build family members and the links between them and residents."""
    resident_id = {r.full_name: r.id for r in residents}
    used = {family for _, family, _, _ in PLANTED_LINKS}
    members: dict[str, tuple[int, str, str, str]] = {}
    links: list[tuple[int, int, str, int]] = []

    def member_id(name: str) -> int:
        if name not in members:
            phone, email = _contact(rng, name)
            members[name] = (len(members) + 1, name, phone, email)
        return members[name][0]

    for resident, family, relationship, billing in PLANTED_LINKS:
        links.append(
            (resident_id[resident], member_id(family), relationship, int(billing))
        )

    planted = {name for name, _ in PLANTED_RESIDENTS}
    for resident in residents:
        if resident.full_name in planted:
            continue
        last = resident.full_name.split()[-1]
        for position in range(rng.choices((1, 2, 3, 4), weights=(25, 40, 25, 10))[0]):
            surname = last if rng.random() < 0.7 else fake.last_name()
            name = _unique_name(fake, rng, used, surname)
            relationship = rng.choices(RELATIONSHIPS, weights=RELATIONSHIP_WEIGHTS)[0]
            billing = position == 0 or rng.random() < 0.25
            links.append((resident.id, member_id(name), relationship, int(billing)))
    return list(members.values()), links


def make_schedule(
    rng: random.Random, residents: list[Resident], staff: list[Staff]
) -> list[tuple[int, int, str, str, str]]:
    """Build two weeks of care schedule. Only Edith Carter is double-booked."""
    by_title = {t: [s.id for s in staff if s.job_title == t] for t in set(STAFF_TITLES)}
    days = [
        REFERENCE_DATE + timedelta(days=d) for d in range(-DAYS_BEFORE, DAYS_AFTER + 1)
    ]
    items: list[tuple[int, int, str, str, str]] = []
    taken: set[tuple[int, str]] = set()

    def add(
        resident: int, when: str, kind: str, text: str, title: str, force: bool = False
    ) -> None:
        if not force and (resident, when) in taken:
            return
        taken.add((resident, when))
        items.append((resident, rng.choice(by_title[title]), when, kind, text))

    edith = next(r.id for r in residents if r.full_name == "Edith Carter")
    clash_day = REFERENCE_DATE + timedelta(days=1)
    add(
        edith,
        _moment(clash_day, 14),
        "physiotherapy",
        "Physiotherapy session",
        "physiotherapist",
    )
    add(
        edith,
        _moment(clash_day, 14),
        "appointment",
        "Visiting doctor appointment",
        "nurse",
        force=True,
    )

    for resident in residents:
        physio_days = set(rng.sample(range(7), 2)) if rng.random() < 0.4 else set()
        appointment_day = rng.choice(days) if rng.random() < 0.4 else None
        appointment_hour = rng.randint(10, 16)
        appointment_text = rng.choice(APPOINTMENTS)
        needs_help = resident.care_level != "independent"
        for day in days:
            add(
                resident.id,
                _moment(day, 8),
                "medication_round",
                "Morning medication round",
                "nurse",
            )
            add(
                resident.id,
                _moment(day, 20),
                "medication_round",
                "Evening medication round",
                "nurse",
            )
            if needs_help:
                add(
                    resident.id,
                    _moment(day, 8, 30),
                    "personal_care",
                    "Morning personal care",
                    "caregiver",
                )
                add(
                    resident.id,
                    _moment(day, 12),
                    "meal_assistance",
                    "Lunch assistance",
                    "caregiver",
                )
                add(
                    resident.id,
                    _moment(day, 19),
                    "personal_care",
                    "Evening personal care",
                    "caregiver",
                )
            if day.weekday() in physio_days:
                add(
                    resident.id,
                    _moment(day, 14),
                    "physiotherapy",
                    "Physiotherapy session",
                    "physiotherapist",
                )
            if day == appointment_day:
                add(
                    resident.id,
                    _moment(day, appointment_hour),
                    "appointment",
                    appointment_text,
                    "nurse",
                )
    return items


def make_activities(rng: random.Random) -> list[tuple[str, str, str, int]]:
    """Build three shared activities per day, plus a service on Sundays."""
    rows: list[tuple[str, str, str, int]] = []
    for offset in range(-DAYS_BEFORE, DAYS_AFTER + 1):
        day = REFERENCE_DATE + timedelta(days=offset)
        for hour, (title, place, minutes) in zip(
            (11, 14, 16), rng.sample(ACTIVITY_TEMPLATES, 3), strict=True
        ):
            rows.append((title, place, _moment(day, hour), minutes))
        if day.weekday() == 6:
            rows.append(("Worship service", "Chapel", _moment(day, 10), 60))
    return rows


def make_visits(
    rng: random.Random,
    residents: list[Resident],
    family: list[tuple[int, str, str, str]],
    links: list[tuple[int, int, str, int]],
) -> list[tuple[int, int, str, str]]:
    """Build family visits. Visiting hours are 10:00 to 18:00."""
    resident_id = {r.full_name: r.id for r in residents}
    family_id = {name: fid for fid, name, _, _ in family}
    rows: list[tuple[int, int, str, str]] = []
    seen: set[tuple[int, int, str]] = set()

    def add(resident: int, member: int, when: str, status: str) -> None:
        if (resident, member, when) not in seen:
            seen.add((resident, member, when))
            rows.append((resident, member, when, status))

    # Planted: a visit today, and a cancelled visit tomorrow.
    add(
        resident_id["Mary Johnson"],
        family_id["Karen Mitchell"],
        _moment(REFERENCE_DATE, 15),
        "scheduled",
    )
    add(
        resident_id["Marie Johnson"],
        family_id["Tom Johnson"],
        _moment(REFERENCE_DATE + timedelta(days=1), 11),
        "cancelled",
    )

    for resident, member, _, _ in links:
        for _ in range(rng.choice((0, 0, 1, 1, 2, 3))):
            day = REFERENCE_DATE + timedelta(days=rng.randint(-DAYS_BEFORE, DAYS_AFTER))
            when = _moment(day, rng.randint(10, 17), rng.choice((0, 30)))
            past = day < REFERENCE_DATE
            if rng.random() < (0.15 if past else 0.10):
                status = "cancelled"
            else:
                status = "completed" if past else "scheduled"
            add(resident, member, when, status)
    return rows


def make_incidents(
    rng: random.Random, residents: list[Resident], staff: list[Staff]
) -> list[tuple[int, int | None, str, str, str, str]]:
    """Build 12 incidents over the last 60 days; the newest 4 still need action."""
    reporters = [s.id for s in staff if s.job_title in ("nurse", "caregiver")]
    harold = next(r.id for r in residents if r.full_name == "Harold Bennett")
    categories = (
        ["fall"] * 3
        + ["missing_belongings"] * 2
        + ["complaint"] * 3
        + ["behaviour"] * 2
        + ["emergency"]
    )
    rng.shuffle(categories)
    drafts: list[tuple[str, int, str]] = [
        (_moment(REFERENCE_DATE - timedelta(days=2), 9, 40), harold, "fall")
    ]
    for category in categories:
        day = REFERENCE_DATE - timedelta(days=rng.randint(1, 60))
        drafts.append(
            (
                _moment(day, rng.randint(7, 21), rng.choice((0, 15, 30, 45))),
                rng.choice(residents).id,
                category,
            )
        )
    drafts.sort(reverse=True)
    rows = []
    for rank, (when, resident, category) in enumerate(drafts):
        reporter = None if category == "emergency" else rng.choice(reporters)
        status = "needs_action" if rank < 4 and category != "emergency" else "resolved"
        rows.append(
            (resident, reporter, when, category, INCIDENT_TEXT[category], status)
        )
    return rows


def make_billing(
    rng: random.Random, residents: list[Resident]
) -> list[tuple[int, str, int, str]]:
    """Build three monthly invoices per resident."""
    rows = []
    for resident in residents:
        fee = MONTHLY_FEE_CENTS[resident.care_level]
        rows.append((resident.id, "2026-08", fee, "paid"))
        rows.append(
            (resident.id, "2026-09", fee, "paid" if rng.random() < 0.8 else "overdue")
        )
        rows.append((resident.id, "2026-10", fee, "unpaid"))
    return rows


def build_database(output: Path) -> dict[str, int]:
    """Create the database file at ``output`` and return the row count per table."""
    fake = Faker("en_US")
    fake.seed_instance(SEED)
    rng = random.Random(SEED)

    residents = make_residents(fake, rng)
    staff = make_staff(fake, rng)
    family, links = make_family(fake, rng, residents)
    schedule = make_schedule(rng, residents, staff)
    activities = make_activities(rng)
    visits = make_visits(rng, residents, family, links)
    incidents = make_incidents(rng, residents, staff)
    billing = make_billing(rng, residents)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    conn = sqlite3.connect(output)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_PATH.read_text())
        conn.executemany("INSERT INTO residents VALUES (?, ?, ?, ?, ?)", residents)
        conn.executemany("INSERT INTO staff VALUES (?, ?, ?)", staff)
        conn.executemany("INSERT INTO family_members VALUES (?, ?, ?, ?)", family)
        conn.executemany("INSERT INTO family_links VALUES (?, ?, ?, ?)", links)
        conn.executemany(
            "INSERT INTO schedule_items (resident_id, staff_id, scheduled_for, kind, description) VALUES (?, ?, ?, ?, ?)",
            schedule,
        )
        conn.executemany(
            "INSERT INTO activities (title, location, starts_at, duration_minutes) VALUES (?, ?, ?, ?)",
            activities,
        )
        conn.executemany(
            "INSERT INTO visits (resident_id, family_member_id, scheduled_for, status) VALUES (?, ?, ?, ?)",
            visits,
        )
        conn.executemany(
            "INSERT INTO incidents (resident_id, reported_by_staff_id, occurred_at, category, description, status) VALUES (?, ?, ?, ?, ?, ?)",
            incidents,
        )
        conn.executemany(
            "INSERT INTO billing (resident_id, period, amount_cents, status) VALUES (?, ?, ?, ?)",
            billing,
        )
        conn.commit()
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES
        }
    finally:
        conn.close()


def main() -> None:
    """Parse arguments, build the database, and print a summary."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="database file to create"
    )
    args = parser.parse_args()
    counts = build_database(args.output)
    print(f"Created {args.output}")
    for table, count in counts.items():
        print(f"  {table:<16}{count:>6}")


if __name__ == "__main__":
    main()
