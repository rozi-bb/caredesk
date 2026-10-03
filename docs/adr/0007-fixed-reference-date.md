# ADR-0007: Fixed reference date for "today"

- Status: Accepted
- Date: 2026-10-03

## Context

Many questions are relative to today ("what is on this afternoon?"). With the real date, the right answer changes every day, and evaluation results cannot be compared between runs.

## Decision

The data has a fixed "today": 2026-10-05, defined as `REFERENCE_DATE` in `src/agent/db`. Tools use it instead of the system clock.

## Alternatives considered

- **Real date, data generated relative to it**: the content shifts daily and evaluation datasets go stale.
- **Real date, static data**: "today" soon falls outside the data.

## Consequences

- Answers and evaluation results are reproducible.
- With real data, the date must come from the clock. Replacing it is a deliberate step before any real use.
