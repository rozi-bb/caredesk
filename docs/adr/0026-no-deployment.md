# ADR-0026: CareDesk runs locally only; no deployment

- Status: Accepted; monitoring steps 24 and 26 dropped by [ADR-0032](0032-no-quality-or-error-monitoring.md)
- Date: 2026-10-13
- Replaces the "package C comes later" part of [ADR-0019](0019-release-2-thin-local-app.md)

## Context

ADR-0019 put deployment (playbook steps 20–23: server, domain, HTTPS, production keys, backups, release procedure) in a later package C. CareDesk is a portfolio project. Nobody else needs to use it online, and the project owner does not want to pay for a server.

## Decision

CareDesk is never deployed. Steps 20–23 are not planned. Monitoring (steps 24–26) stays, run on the local app: LangSmith tracing already works locally, and usage is already recorded per user.

## Alternatives considered

- **A VPS with a domain**: monthly cost and server upkeep for an app nobody else uses.
- **A free hosting tier**: still needs a hosted Postgres and the model key on someone else's server, for little gain.

## Consequences

- The app is shown by running it locally, following the README.
- Rate limiting is not needed: only the owner can reach the app.
- Choices still should not block deployment later (no dependency on paid hosting), but nothing is built for it now.
