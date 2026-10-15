"""Generate the synthetic Evergreen Care Home database.

Everything comes from one fixed seed, so running this twice produces the
same data (with the Faker version pinned in uv.lock). All people are
fictional and every phone number is in the reserved fictional 555-01xx range.

The database is rebuilt from scratch: the schema is dropped, migrated to the
latest version, and filled. This also deletes accounts and conversations.
Every staff and family member gets an account; their demo passwords are
random and written to a git-ignored file (ADR-0022).

Usage:
    uv run python scripts/seed_db.py [--database-url URL] [--demo-password PW]
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import secrets
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import NamedTuple

import psycopg
from alembic import command
from alembic.config import Config
from faker import Faker

from agent.db import REFERENCE_DATE, database_url
from backend.security import hash_password

SEED = 42
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ACCOUNTS_FILE = ROOT / "data" / "demo_accounts.csv"
STAFF_EMAIL_DOMAIN = "staff.example.org"

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
    "accounts",
)
# Tables whose ids the seed sets itself; their id sequences must be moved past them.
EXPLICIT_IDS = ("residents", "staff", "family_members")

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
    ("Gentle stretching", "Lounge", 45),
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


def _email_slug(name: str) -> str:
    return re.sub(r"[^a-z.]", "", name.lower().replace(" ", "."))


def _contact(rng: random.Random, name: str) -> tuple[str, str]:
    return f"555-01{rng.randint(0, 99):02d}", f"{_email_slug(name)}@example.org"


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
    """Build 11 incidents over the last 60 days; the newest 4 still need action."""
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
        # Emergencies are no longer recorded (ADR-0030). The draft is still made
        # and dropped here, so the random numbers behind all later data, and
        # the expected answers stored in the evaluation datasets, stay the same.
        if category == "emergency":
            continue
        reporter = rng.choice(reporters)
        status = "needs_action" if rank < 4 else "resolved"
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


class Account(NamedTuple):
    """A sign-in account for one staff or family member."""

    email: str
    password: str
    role: str
    staff_id: int | None
    family_member_id: int | None
    full_name: str


def make_accounts(
    staff: list[Staff],
    family: list[tuple[int, str, str, str]],
    demo_password: str | None,
) -> list[Account]:
    """Build one account per staff and family member.

    Passwords are random unless a demo password is given (tests use one), and
    never come from the seed, so they cannot be derived from the code.
    """

    def password() -> str:
        return demo_password or secrets.token_urlsafe(12)

    accounts = [
        Account(
            f"{_email_slug(s.full_name)}@{STAFF_EMAIL_DOMAIN}",
            password(),
            "staff",
            s.id,
            None,
            s.full_name,
        )
        for s in staff
    ]
    accounts += [
        Account(email, password(), "family", None, fid, name)
        for fid, name, _, email in family
    ]
    return accounts


def reset_schema(url: str) -> None:
    """Drop everything in the database and migrate it to the latest schema."""
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")


def build_database(
    url: str, accounts_file: Path | None = None, demo_password: str | None = None
) -> dict[str, int]:
    """Rebuild the database at ``url`` and return the row count per table."""
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
    accounts = make_accounts(staff, family, demo_password)

    reset_schema(url)
    shared_hash = hash_password(demo_password) if demo_password else None
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.executemany("INSERT INTO residents VALUES (%s, %s, %s, %s, %s)", residents)
        cur.executemany("INSERT INTO staff VALUES (%s, %s, %s)", staff)
        cur.executemany("INSERT INTO family_members VALUES (%s, %s, %s, %s)", family)
        cur.executemany(
            "INSERT INTO family_links VALUES (%s, %s, %s, %s)",
            [(r, f, rel, bool(b)) for r, f, rel, b in links],
        )
        cur.executemany(
            "INSERT INTO schedule_items (resident_id, staff_id, scheduled_for, kind, description) "
            "VALUES (%s, %s, %s, %s, %s)",
            schedule,
        )
        cur.executemany(
            "INSERT INTO activities (title, location, starts_at, duration_minutes) "
            "VALUES (%s, %s, %s, %s)",
            activities,
        )
        cur.executemany(
            "INSERT INTO visits (resident_id, family_member_id, scheduled_for, status) "
            "VALUES (%s, %s, %s, %s)",
            visits,
        )
        cur.executemany(
            "INSERT INTO incidents (resident_id, reported_by_staff_id, occurred_at, category, description, status) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            incidents,
        )
        cur.executemany(
            "INSERT INTO billing (resident_id, period, amount_cents, status) VALUES (%s, %s, %s, %s)",
            billing,
        )
        cur.executemany(
            "INSERT INTO accounts (email, password_hash, role, staff_id, family_member_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            [
                (
                    a.email,
                    shared_hash or hash_password(a.password),
                    a.role,
                    a.staff_id,
                    a.family_member_id,
                )
                for a in accounts
            ],
        )
        for table in EXPLICIT_IDS:
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), max(id)) FROM {table}"
            )
        counts = {}
        for table in TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            row = cur.fetchone()
            counts[table] = row[0] if row else 0

    if accounts_file:
        accounts_file.parent.mkdir(parents=True, exist_ok=True)
        with accounts_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["email", "password", "role", "name"])
            writer.writerows(
                (a.email, a.password, a.role, a.full_name) for a in accounts
            )
        accounts_file.chmod(0o600)
    return counts


def main() -> None:
    """Parse arguments, rebuild the database, and print a summary."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", default=None, help="defaults to DATABASE_URL")
    parser.add_argument(
        "--demo-password",
        default=None,
        help="give every account this password instead of a random one",
    )
    parser.add_argument(
        "--accounts-file",
        type=Path,
        default=DEFAULT_ACCOUNTS_FILE,
        help="where to write the demo accounts and passwords",
    )
    args = parser.parse_args()
    url = args.database_url or database_url()
    counts = build_database(url, args.accounts_file, args.demo_password)
    print(f"Rebuilt the database at {url.rsplit('@', 1)[-1]}")
    for table, count in counts.items():
        print(f"  {table:<16}{count:>6}")
    print(f"Demo accounts and passwords: {args.accounts_file}")


if __name__ == "__main__":
    main()
