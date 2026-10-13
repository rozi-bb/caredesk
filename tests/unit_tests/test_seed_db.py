from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

from backend.security import verify_password

OPERATIONAL_TABLES = (
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


@pytest.fixture(scope="module")
def db(db_url: str) -> Iterator[psycopg.Connection[Any]]:
    conn = psycopg.connect(db_url)
    conn.read_only = True
    yield conn
    conn.close()


def dump(url: str) -> dict[str, list[Any]]:
    with psycopg.connect(url) as conn:
        tables = {
            t: conn.execute(f"SELECT * FROM {t} ORDER BY 1, 2, 3").fetchall()
            for t in OPERATIONAL_TABLES
        }
        # Password hashes are salted on purpose, so only the account owners are compared.
        tables["accounts"] = conn.execute(
            "SELECT email, role, staff_id, family_member_id FROM accounts ORDER BY email"
        ).fetchall()
        return tables


def test_same_seed_gives_identical_data(db_url: str, make_database) -> None:
    assert dump(db_url) == dump(make_database())


def test_expected_sizes(db: psycopg.Connection[Any]) -> None:
    assert db.execute("SELECT COUNT(*) FROM residents").fetchone() == (30,)
    assert db.execute("SELECT COUNT(*) FROM staff").fetchone() == (15,)


def test_visits_must_belong_to_a_family_link(db_url: str) -> None:
    with psycopg.connect(db_url) as conn:
        unlinked = conn.execute(
            "SELECT r.id, f.id FROM residents r CROSS JOIN family_members f "
            "WHERE NOT EXISTS (SELECT 1 FROM family_links l "
            "WHERE l.resident_id = r.id AND l.family_member_id = f.id) LIMIT 1"
        ).fetchone()
        assert unlinked is not None
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute(
                "INSERT INTO visits (resident_id, family_member_id, scheduled_for, status) "
                "VALUES (%s, %s, '2026-10-05 10:00', 'scheduled')",
                unlinked,
            )
        conn.rollback()


def test_near_identical_resident_names(db: psycopg.Connection[Any]) -> None:
    names = {r[0] for r in db.execute("SELECT full_name FROM residents")}
    assert {"Mary Johnson", "Marie Johnson"} <= names


def test_only_one_of_four_children_sees_billing(db: psycopg.Connection[Any]) -> None:
    rows = db.execute(
        "SELECT can_view_billing FROM family_links l "
        "JOIN residents r ON r.id = l.resident_id WHERE r.full_name = 'Harold Bennett'"
    ).fetchall()
    assert len(rows) == 4
    assert sum(1 for (flag,) in rows if flag) == 1


def test_resident_without_family(db: psycopg.Connection[Any]) -> None:
    count = db.execute(
        "SELECT COUNT(*) FROM family_links l JOIN residents r ON r.id = l.resident_id "
        "WHERE r.full_name = 'Dorothy Hale'"
    ).fetchone()
    assert count == (0,)


def test_family_member_with_different_access_per_resident(
    db: psycopg.Connection[Any],
) -> None:
    flags = db.execute(
        "SELECT l.can_view_billing FROM family_links l "
        "JOIN family_members f ON f.id = l.family_member_id "
        "WHERE f.full_name = 'Linda Moreno'"
    ).fetchall()
    assert sorted(flag for (flag,) in flags) == [False, True]


def test_staff_and_family_member_share_a_name(db: psycopg.Connection[Any]) -> None:
    in_staff = db.execute(
        "SELECT COUNT(*) FROM staff WHERE full_name = 'Karen Mitchell'"
    ).fetchone()
    in_family = db.execute(
        "SELECT COUNT(*) FROM family_members WHERE full_name = 'Karen Mitchell'"
    ).fetchone()
    assert (in_staff, in_family) == ((1,), (1,))


def test_exactly_one_double_booked_slot(db: psycopg.Connection[Any]) -> None:
    clashes = db.execute(
        "SELECT resident_id, scheduled_for FROM schedule_items "
        "GROUP BY resident_id, scheduled_for HAVING COUNT(*) > 1"
    ).fetchall()
    assert len(clashes) == 1


def test_cancelled_visit_and_open_incident_exist(db: psycopg.Connection[Any]) -> None:
    cancelled = db.execute(
        "SELECT COUNT(*) FROM visits WHERE status = 'cancelled'"
    ).fetchone()
    open_incidents = db.execute(
        "SELECT COUNT(*) FROM incidents WHERE status = 'needs_action'"
    ).fetchone()
    assert cancelled is not None and cancelled[0] >= 1
    assert open_incidents is not None and open_incidents[0] >= 2


def test_medication_rounds_carry_no_clinical_detail(
    db: psycopg.Connection[Any],
) -> None:
    texts = {
        r[0]
        for r in db.execute(
            "SELECT DISTINCT description FROM schedule_items WHERE kind = 'medication_round'"
        )
    }
    assert texts == {"Morning medication round", "Evening medication round"}


def test_contact_details_are_fictional(db: psycopg.Connection[Any]) -> None:
    phones = [r[0] for r in db.execute("SELECT phone FROM family_members")]
    emails = [r[0] for r in db.execute("SELECT email FROM accounts")]
    assert all(p.startswith("555-01") for p in phones)
    assert all(e.endswith("example.org") for e in emails)


def test_every_staff_and_family_member_has_one_account(
    db: psycopg.Connection[Any],
) -> None:
    missing = db.execute(
        "SELECT (SELECT COUNT(*) FROM staff s WHERE NOT EXISTS "
        "(SELECT 1 FROM accounts a WHERE a.staff_id = s.id)) + "
        "(SELECT COUNT(*) FROM family_members f WHERE NOT EXISTS "
        "(SELECT 1 FROM accounts a WHERE a.family_member_id = f.id))"
    ).fetchone()
    assert missing == (0,)


def test_passwords_are_stored_only_as_hashes(
    db: psycopg.Connection[Any], test_password: str
) -> None:
    row = db.execute("SELECT password_hash FROM accounts LIMIT 1").fetchone()
    assert row is not None
    assert test_password not in row[0]
    assert verify_password(row[0], test_password)
