import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "seed_db.py"


def seed(output: Path) -> None:
    subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        check=True,
        capture_output=True,
    )


def dump(output: Path) -> str:
    conn = sqlite3.connect(output)
    try:
        return "\n".join(conn.iterdump())
    finally:
        conn.close()


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> Iterator[sqlite3.Connection]:
    path = tmp_path_factory.mktemp("seed") / "caredesk.db"
    seed(path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


def test_same_seed_gives_identical_database(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    second = tmp_path / "second.db"
    seed(second)
    first_path = Path(db.execute("PRAGMA database_list").fetchone()[2])
    assert dump(first_path) == dump(second)


def test_expected_sizes(db: sqlite3.Connection) -> None:
    assert db.execute("SELECT COUNT(*) FROM residents").fetchone()[0] == 30
    assert db.execute("SELECT COUNT(*) FROM staff").fetchone()[0] == 15


def test_no_broken_relations(db: sqlite3.Connection) -> None:
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_near_identical_resident_names(db: sqlite3.Connection) -> None:
    names = {r[0] for r in db.execute("SELECT full_name FROM residents")}
    assert {"Mary Johnson", "Marie Johnson"} <= names


def test_only_one_of_four_children_sees_billing(db: sqlite3.Connection) -> None:
    rows = db.execute(
        "SELECT can_view_billing FROM family_links l "
        "JOIN residents r ON r.id = l.resident_id WHERE r.full_name = 'Harold Bennett'"
    ).fetchall()
    assert len(rows) == 4
    assert sum(flag for (flag,) in rows) == 1


def test_resident_without_family(db: sqlite3.Connection) -> None:
    count = db.execute(
        "SELECT COUNT(*) FROM family_links l JOIN residents r ON r.id = l.resident_id "
        "WHERE r.full_name = 'Dorothy Hale'"
    ).fetchone()[0]
    assert count == 0


def test_family_member_with_different_access_per_resident(
    db: sqlite3.Connection,
) -> None:
    flags = db.execute(
        "SELECT l.can_view_billing FROM family_links l "
        "JOIN family_members f ON f.id = l.family_member_id "
        "WHERE f.full_name = 'Linda Moreno'"
    ).fetchall()
    assert sorted(flag for (flag,) in flags) == [0, 1]


def test_staff_and_family_member_share_a_name(db: sqlite3.Connection) -> None:
    in_staff = db.execute(
        "SELECT COUNT(*) FROM staff WHERE full_name = 'Karen Mitchell'"
    ).fetchone()[0]
    in_family = db.execute(
        "SELECT COUNT(*) FROM family_members WHERE full_name = 'Karen Mitchell'"
    ).fetchone()[0]
    assert (in_staff, in_family) == (1, 1)


def test_exactly_one_double_booked_slot(db: sqlite3.Connection) -> None:
    clashes = db.execute(
        "SELECT resident_id, scheduled_for FROM schedule_items "
        "GROUP BY resident_id, scheduled_for HAVING COUNT(*) > 1"
    ).fetchall()
    assert len(clashes) == 1


def test_cancelled_visit_and_open_incident_exist(db: sqlite3.Connection) -> None:
    cancelled = db.execute(
        "SELECT COUNT(*) FROM visits WHERE status = 'cancelled'"
    ).fetchone()[0]
    open_incidents = db.execute(
        "SELECT COUNT(*) FROM incidents WHERE status = 'needs_action'"
    ).fetchone()[0]
    assert cancelled >= 1
    assert open_incidents >= 2


def test_medication_rounds_carry_no_clinical_detail(db: sqlite3.Connection) -> None:
    texts = {
        r[0]
        for r in db.execute(
            "SELECT DISTINCT description FROM schedule_items WHERE kind = 'medication_round'"
        )
    }
    assert texts == {"Morning medication round", "Evening medication round"}


def test_contact_details_are_fictional(db: sqlite3.Connection) -> None:
    phones = [r[0] for r in db.execute("SELECT phone FROM family_members")]
    emails = [r[0] for r in db.execute("SELECT email FROM family_members")]
    assert all(p.startswith("555-01") for p in phones)
    assert all(e.endswith("@example.org") for e in emails)
