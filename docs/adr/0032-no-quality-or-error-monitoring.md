# ADR-0032: No quality or error monitoring while nobody else uses the app

- Status: Accepted
- Date: 2026-10-16
- Replaces the "monitoring (steps 24–26) stays" part of [ADR-0026](0026-no-deployment.md) for steps 24 and 26

## Context

ADR-0026 kept monitoring (playbook steps 24–26) on the local app. Monitoring needs traffic from real users to show anything. CareDesk is never deployed, so the only conversations are the owner's own tests.

## Decision

Steps 24 (quality monitoring: Insights, user feedback) and 26 (error monitoring, spending alert at the model provider) are not planned. Step 25, cost per user, stays: it is computed from usage records and trace metadata that already exist.

## Alternatives considered

- **Build steps 24 and 26 anyway**: shows the setup, but Insights over a handful of test conversations and a feedback button nobody else presses produce no useful data.
- **Build only the feedback button**: small, but the same problem; without users there is nothing to collect.

## Consequences

- Errors are still visible in LangSmith traces, which already run locally.
- The DeepSeek account is prepaid, so spending cannot pass the balance. Whether DeepSeek offers a spending alert was not checked.
- If CareDesk ever gets real users, steps 24 and 26 come back: a feedback button that sends scores to LangSmith, a regular Insights run, and failed conversations added as evaluation cases.
