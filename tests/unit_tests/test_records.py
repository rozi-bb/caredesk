import sqlite3
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from agent import records
from agent.context import Context


@pytest.fixture
def conn(db_file: Path) -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(db_file)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def family(conn: sqlite3.Connection, name: str) -> Context:
    row = conn.execute(
        "SELECT id FROM family_members WHERE full_name = ?", (name,)
    ).fetchone()
    return Context(user_id=row["id"], role="family")


def staff(conn: sqlite3.Connection, name: str) -> Context:
    row = conn.execute("SELECT id FROM staff WHERE full_name = ?", (name,)).fetchone()
    return Context(user_id=row["id"], role="staff")


def names(refs: list[records.ResidentRef]) -> set[str]:
    return {r.full_name for r in refs}


def test_missing_or_unknown_identity_sees_nothing(conn: sqlite3.Connection) -> None:
    assert records.visible_residents(conn, Context()) == []
    assert records.schedule(conn, Context(), "Mary Johnson", "") == records.NO_IDENTITY
    ghost = Context(user_id=9999, role="staff")
    assert records.visible_residents(conn, ghost) == []
    assert records.incidents(conn, ghost, "all") == records.NO_IDENTITY


def test_staff_see_every_resident(conn: sqlite3.Connection) -> None:
    assert len(records.visible_residents(conn, staff(conn, "Karen Mitchell"))) == 30


def test_family_see_only_linked_residents(conn: sqlite3.Connection) -> None:
    linda = family(conn, "Linda Moreno")
    assert names(records.visible_residents(conn, linda)) == {
        "Rosa Moreno",
        "Hector Alvarez",
    }


def test_family_cannot_read_an_unlinked_resident(conn: sqlite3.Connection) -> None:
    tom = family(conn, "Tom Johnson")  # linked to Marie Johnson only
    reply = records.schedule(conn, tom, "Mary Johnson", "")
    assert (
        reply
        == "No resident you have access to matches 'Mary Johnson'. Did you mean: Marie Johnson?"
    )
    assert "medication" not in reply


def test_unlinked_and_nonexistent_residents_look_the_same(
    conn: sqlite3.Connection,
) -> None:
    tom = family(conn, "Tom Johnson")
    unlinked = records.billing(conn, tom, "Dorothy Hale")
    nonexistent = records.billing(conn, tom, "Nobody Here")
    assert unlinked == "No resident you have access to matches 'Dorothy Hale'."
    assert nonexistent == "No resident you have access to matches 'Nobody Here'."


def test_near_identical_names_are_never_guessed(conn: sqlite3.Connection) -> None:
    nurse = staff(conn, "Karen Mitchell")
    assert records.resolve_resident(conn, nurse, "Mary Johnson") == next(
        r
        for r in records.visible_residents(conn, nurse)
        if r.full_name == "Mary Johnson"
    )
    ambiguous = records.resolve_resident(conn, nurse, "Mrs Johnson")
    assert isinstance(ambiguous, str)
    assert "Mary Johnson" in ambiguous and "Marie Johnson" in ambiguous
    typo = records.resolve_resident(conn, nurse, "Mary Jonson")
    assert (
        isinstance(typo, str)
        and typo.startswith("No resident")
        and "Mary Johnson" in typo
    )


def test_empty_name_means_the_family_members_own_resident(
    conn: sqlite3.Connection,
) -> None:
    karen = family(conn, "Karen Mitchell")
    assert records.schedule(conn, karen, "", "today").startswith(
        "Schedule for Mary Johnson"
    )


def test_family_with_two_residents_must_choose(conn: sqlite3.Connection) -> None:
    linda = family(conn, "Linda Moreno")
    reply = records.schedule(conn, linda, "", "")
    assert reply.startswith("Please say which resident you mean")


def test_billing_needs_the_billing_permission(conn: sqlite3.Connection) -> None:
    anne = family(conn, "Anne Bennett")
    peter = family(conn, "Peter Bennett")
    denied = records.billing(conn, anne, "Harold Bennett")
    assert denied == "You do not have permission to see billing for Harold Bennett."
    assert "$" not in denied
    assert "$5,600.00" in records.billing(conn, peter, "Harold Bennett")


def test_one_family_member_with_different_access_per_resident(
    conn: sqlite3.Connection,
) -> None:
    linda = family(conn, "Linda Moreno")
    assert "$" in records.billing(conn, linda, "Rosa Moreno")
    assert "permission" in records.billing(conn, linda, "Hector Alvarez")


def test_incidents_are_staff_only_even_with_a_staff_name(
    conn: sqlite3.Connection,
) -> None:
    as_family = family(conn, "Karen Mitchell")
    as_staff = staff(conn, "Karen Mitchell")
    assert records.incidents(conn, as_family, "needs_action") == records.STAFF_ONLY
    assert "Harold Bennett" in records.incidents(conn, as_staff, "needs_action")


def test_relative_days_use_the_reference_date(conn: sqlite3.Connection) -> None:
    assert records.parse_day("tomorrow") == date(2026, 10, 6)
    reply = records.schedule(
        conn, staff(conn, "Karen Mitchell"), "Edith Carter", "tomorrow"
    )
    assert reply.count("14:00") == 2


def test_resident_info_respects_scope(conn: sqlite3.Connection) -> None:
    nurse = staff(conn, "Karen Mitchell")
    assert "room 115" in records.resident_info(conn, nurse, "Marie Johnson")
    tom = family(conn, "Tom Johnson")
    assert records.resident_info(conn, tom, "Dorothy Hale").startswith("No resident")


def test_profile_lists_links_and_billing_access(conn: sqlite3.Connection) -> None:
    profile = records.my_profile(conn, family(conn, "Linda Moreno"))
    assert "Rosa Moreno" in profile and "can see billing" in profile
    assert "Hector Alvarez" in profile and "cannot see billing" in profile
