# ADR-0012: Family members see medication-round times

- Status: Accepted
- Date: 2026-10-03

## Context

prd.md left open whether family members may see medication schedules or only that care is scheduled. The synthetic data records medication only as "Morning medication round" and "Evening medication round": no drug names, doses, or reasons.

## Decision

Family members see the full care schedule of their linked resident, including medication-round times. The data model never stores clinical detail about medication, so there is nothing more to hide.

## Alternatives considered

- **Hide medication rounds from family**: protects nothing extra, and makes the schedule look incomplete ("why is there a gap at 08:00?").
- **Store drug names and show them to staff only**: brings clinical data into a product that must stay administrative.

## Consequences

- One schedule view for both roles, so one code path to test.
- If drug details are ever added to the data, this decision must be revisited before they reach any tool.
