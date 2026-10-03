# ADR-0009: No hard usage limits

- Status: Accepted
- Date: 2026-09-30

## Context

The playbook proposes a usage limit that rejects requests once a user reaches 100% of a budget. In this product a rejected request could be an emergency message (prd.md section 6, rule 4). There is also one customer, so there are no plans to sell.

## Decision

No limit blocks requests. Cost is controlled by monitoring: cost per user from trace metadata, and spend alerts (playbook steps 24 and 25). Pricing is pay-as-you-go.

## Alternatives considered

- **Hard limit per user**: can block an emergency.
- **Hard limit that exempts emergencies**: needs triage to run before the limit; more complexity, kept as an option if abuse becomes real.
- **No cost control at all**: unacceptable for a pay-per-use model.

## Consequences

- Runaway cost is only caught by alerts, so alert thresholds must be set before anyone else uses the system.
- Payments (playbook step 14) are dropped.
