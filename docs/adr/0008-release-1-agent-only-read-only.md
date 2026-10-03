# ADR-0008: Release 1 is agent-only and read-only

- Status: Accepted
- Date: 2026-09-30

## Context

The playbook covers a full product (backend, database, login, payments, UI). The goal of release 1 is a trustworthy agent that can be explained end to end.

## Decision

Release 1 covers playbook steps 1 to 9 plus evaluation (step 16), run locally in LangGraph Studio.

- Users are staff and family; residents come in release 2.
- Identity is simulated through the runtime context.
- The assistant is read-only. Its only write is the incident record created for an emergency.
- Operational data lives in a SQLite file; Postgres arrives with the backend (step 11).

## Alternatives considered

- **Include backend and login now**: longer, and delays the part that matters most.
- **Include write actions with human confirmation**: adds an approval flow; moved to a later release.
- **Multi-agent**: no demonstrated need with a small tool set.

## Consequences

- Identity can be faked by typing it into Studio. That is acceptable locally and unacceptable for anyone else: login must exist before real use.
- Human-in-the-loop confirmation is not demonstrated in release 1.
- The order of later work is decided once release 1 ships.
