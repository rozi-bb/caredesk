import uuid
from datetime import UTC, datetime, timedelta, timezone

import psycopg
import pytest

from backend.costs import (
    JEV_COST_PER_REQUEST,
    Usage,
    build_report,
    deepseek_cost,
    is_peak,
    load_usage,
)

# 2026-10-15 is a Thursday, 2026-10-17 a Saturday.
THURSDAY_PEAK = datetime(2026, 10, 15, 7, 30, tzinfo=UTC)
THURSDAY_OFF_PEAK = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
SATURDAY = datetime(2026, 10, 17, 7, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("at", "expected"),
    [
        (THURSDAY_PEAK, True),
        (THURSDAY_OFF_PEAK, False),
        (SATURDAY, False),
        (datetime(2026, 10, 15, 1, 0, tzinfo=UTC), True),
        (datetime(2026, 10, 15, 4, 0, tzinfo=UTC), False),
        (datetime(2026, 10, 15, 9, 59, tzinfo=UTC), True),
        (datetime(2026, 10, 15, 10, 0, tzinfo=UTC), False),
    ],
)
def test_peak_hours_are_weekday_utc(at: datetime, expected: bool) -> None:
    assert is_peak(at) is expected


def test_peak_is_judged_in_utc_not_local_time() -> None:
    # 14:30 in Jakarta is 07:30 UTC: peak.
    jakarta = timezone(timedelta(hours=7))
    assert is_peak(datetime(2026, 10, 15, 14, 30, tzinfo=jakarta))


def test_deepseek_cost_uses_the_price_for_the_hour() -> None:
    assert deepseek_cost(1_000_000, 1_000_000, THURSDAY_OFF_PEAK) == pytest.approx(0.75)
    assert deepseek_cost(1_000_000, 1_000_000, THURSDAY_PEAK) == pytest.approx(1.50)


def usage(account_id: int, role: str, channel: str, at: datetime) -> Usage:
    return Usage(
        account_id, f"user{account_id}@example.org", role, channel, at, 2000, 100
    )


def test_report_adds_up_per_account_role_and_channel() -> None:
    rows = [
        usage(1, "staff", "web", THURSDAY_OFF_PEAK),
        usage(1, "staff", "telegram", THURSDAY_PEAK),
        usage(2, "family", "web", SATURDAY),
    ]
    report = build_report(rows)

    staff = report.by_account[(1, "user1@example.org", "staff")]
    assert staff.requests == 2
    assert staff.input_tokens == 4000
    assert staff.deepseek == pytest.approx(
        deepseek_cost(2000, 100, THURSDAY_OFF_PEAK)
        + deepseek_cost(2000, 100, THURSDAY_PEAK)
    )
    assert staff.jev == pytest.approx(2 * JEV_COST_PER_REQUEST)
    assert report.by_role["family"].requests == 1
    assert report.by_channel["web"].requests == 2
    assert report.total.requests == 3
    assert report.total.total == pytest.approx(
        sum(line.total for line in report.by_account.values())
    )
    assert report.total.per_request == pytest.approx(report.total.total / 3)


def test_empty_report_has_no_cost() -> None:
    report = build_report([])
    assert report.total.requests == 0
    assert report.total.per_request == 0.0


def test_load_usage_reads_rows_with_their_account(db_url: str) -> None:
    with psycopg.connect(db_url) as conn:
        account_id, email, role = conn.execute(
            "SELECT id, email, role FROM accounts ORDER BY id LIMIT 1"
        ).fetchone() or (0, "", "")
        thread_id = uuid.uuid4()
        conn.execute(
            "INSERT INTO threads (id, account_id) VALUES (%s, %s)",
            (thread_id, account_id),
        )
        conn.execute(
            "INSERT INTO usage_events (account_id, thread_id, input_tokens, output_tokens, "
            "duration_ms, channel) VALUES (%s, %s, 1200, 80, 900, 'telegram')",
            (account_id, thread_id),
        )
        rows = load_usage(conn)
        conn.rollback()

    assert len(rows) == 1
    assert rows[0].account_id == account_id
    assert rows[0].email == email
    assert rows[0].role == role
    assert rows[0].channel == "telegram"
    assert (rows[0].input_tokens, rows[0].output_tokens) == (1200, 80)
