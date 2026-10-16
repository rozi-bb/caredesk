"""Cost of chat requests in US dollars, computed from usage records (ADR-0033).

The figures are estimates. Every DeepSeek input token is priced as a cache
miss, because cache hits are not recorded, so DeepSeek cost is an upper bound.
Jev's tokens are not recorded either, so its cost is a measured average per
request.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import psycopg

PRICES_CHECKED = "2026-10-16"


@dataclass(frozen=True)
class Price:
    """US dollars per million tokens."""

    input: float
    output: float


# deepseek-flash, cache miss: https://api-docs.deepseek.com/quick_start/pricing
DEEPSEEK_PEAK = Price(input=0.30, output=1.20)
DEEPSEEK_OFF_PEAK = Price(input=0.15, output=0.60)
# Monday to Friday only. DeepSeek also bills Chinese public holidays off-peak;
# those are not known here, so they count as normal days.
PEAK_HOURS_UTC = ((1, 4), (6, 10))

# https://typesafe.ai: input only, output is free. 586 tokens is what one
# triage call used when measured on 2026-10-16.
JEV_PRICE = Price(input=0.042, output=0.0)
JEV_INPUT_TOKENS_PER_REQUEST = 586
JEV_COST_PER_REQUEST = JEV_INPUT_TOKENS_PER_REQUEST * JEV_PRICE.input / 1_000_000


@dataclass(frozen=True)
class Usage:
    """One chat request from `usage_events`, with its account."""

    account_id: int
    email: str
    role: str
    channel: str
    created_at: datetime
    input_tokens: int
    output_tokens: int


@dataclass
class CostLine:
    """Requests, tokens, and cost added up for one row of the report."""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    deepseek: float = 0.0
    jev: float = 0.0

    @property
    def total(self) -> float:
        """DeepSeek and Jev cost together."""
        return self.deepseek + self.jev

    @property
    def per_request(self) -> float:
        """Average total cost of one request, or 0 with no requests."""
        return self.total / self.requests if self.requests else 0.0

    def add(self, usage: Usage) -> None:
        """Count one request in this line."""
        self.requests += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.deepseek += deepseek_cost(
            usage.input_tokens, usage.output_tokens, usage.created_at
        )
        self.jev += JEV_COST_PER_REQUEST


@dataclass
class CostReport:
    """Cost per account, per role, per channel, and in total."""

    by_account: dict[tuple[int, str, str], CostLine] = field(default_factory=dict)
    by_role: dict[str, CostLine] = field(default_factory=dict)
    by_channel: dict[str, CostLine] = field(default_factory=dict)
    total: CostLine = field(default_factory=CostLine)


def is_peak(at: datetime) -> bool:
    """Whether DeepSeek bills a request made at this moment at the peak price."""
    utc = at.astimezone(UTC)
    if utc.weekday() >= 5:
        return False
    return any(start <= utc.hour < end for start, end in PEAK_HOURS_UTC)


def deepseek_cost(input_tokens: int, output_tokens: int, at: datetime) -> float:
    """US dollars for one request's DeepSeek tokens, all input as cache misses."""
    price = DEEPSEEK_PEAK if is_peak(at) else DEEPSEEK_OFF_PEAK
    return (input_tokens * price.input + output_tokens * price.output) / 1_000_000


def build_report(usage: Iterable[Usage]) -> CostReport:
    """Add up every request into the report's lines."""
    report = CostReport()
    for row in usage:
        account = (row.account_id, row.email, row.role)
        report.by_account.setdefault(account, CostLine()).add(row)
        report.by_role.setdefault(row.role, CostLine()).add(row)
        report.by_channel.setdefault(row.channel, CostLine()).add(row)
        report.total.add(row)
    return report


def load_usage(conn: psycopg.Connection[Any]) -> list[Usage]:
    """Read every usage row with its account's email and role, oldest first."""
    rows = conn.execute(
        """
        SELECT u.account_id, a.email, a.role, u.channel, u.created_at,
               u.input_tokens, u.output_tokens
        FROM usage_events u
        JOIN accounts a ON a.id = u.account_id
        ORDER BY u.created_at
        """
    ).fetchall()
    return [Usage(*row) for row in rows]
