"""Print the estimated cost of CareDesk per account, role, and channel (ADR-0033).

Reads `usage_events` and turns tokens into US dollars with the prices in
`backend/costs.py`. Read-only: nothing in the database changes.

Usage:
    uv run python scripts/cost_report.py [--database-url URL]
"""

from __future__ import annotations

import argparse

import psycopg

from agent.db import database_url
from backend.costs import (
    DEEPSEEK_OFF_PEAK,
    DEEPSEEK_PEAK,
    JEV_INPUT_TOKENS_PER_REQUEST,
    PRICES_CHECKED,
    CostLine,
    build_report,
    load_usage,
)


def table(title: str, rows: list[tuple[str, CostLine]]) -> None:
    """Print one section of the report, with the label column as wide as needed."""
    width = max(len(label) for label, _ in rows)
    print(title)
    print(
        f"{'':<{width}} {'requests':>8} {'input':>9} {'output':>8} {'cost $':>9} {'per req $':>10}"
    )
    for label, cost in rows:
        print(
            f"{label:<{width}} {cost.requests:>8} {cost.input_tokens:>9} "
            f"{cost.output_tokens:>8} {cost.total:>9.4f} {cost.per_request:>10.5f}"
        )
    print()


def main() -> None:
    """Read usage, compute cost, and print the report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", default=None, help="defaults to DATABASE_URL")
    args = parser.parse_args()

    with psycopg.connect(args.database_url or database_url()) as conn:
        conn.read_only = True
        usage = load_usage(conn)
    if not usage:
        print("No usage recorded yet.")
        return
    report = build_report(usage)

    print(
        f"CareDesk cost, {usage[0].created_at:%Y-%m-%d} to {usage[-1].created_at:%Y-%m-%d}"
    )
    print()
    accounts = sorted(report.by_account.items(), key=lambda item: -item[1].total)
    table(
        "Per account",
        [
            (f"{account_id} {email} ({role})", cost)
            for (account_id, email, role), cost in accounts
        ],
    )
    table("Per role", sorted(report.by_role.items()))
    table("Per channel", sorted(report.by_channel.items()))
    total = report.total
    print(
        f"Total: {total.requests} requests, ${total.total:.4f} "
        f"(DeepSeek ${total.deepseek:.4f}, Jev ${total.jev:.4f}), "
        f"${total.per_request:.5f} per request"
    )
    print()
    print(
        f"Prices checked {PRICES_CHECKED}. deepseek-flash per million tokens, off-peak/peak: "
        f"input ${DEEPSEEK_OFF_PEAK.input:.2f}/${DEEPSEEK_PEAK.input:.2f}, "
        f"output ${DEEPSEEK_OFF_PEAK.output:.2f}/${DEEPSEEK_PEAK.output:.2f}."
    )
    print(
        "Every input token is priced as a cache miss, so DeepSeek cost is an upper bound."
    )
    print(
        f"Jev is an estimate: {JEV_INPUT_TOKENS_PER_REQUEST} input tokens per request."
    )


if __name__ == "__main__":
    main()
