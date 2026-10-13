# ADR-0021: One Postgres database for all app data

- Status: Accepted
- Date: 2026-10-13

## Context

Release 1 keeps operational data in a SQLite file, and the Agent Server keeps conversations. Release 2 needs Postgres for the checkpointer (ADR-0020), plus new tables for accounts and usage.

## Decision

All app data lives in one Postgres database: operational data (moved from SQLite), accounts, usage records, and conversation checkpoints. Schema changes are written as migration files and committed, never applied by hand. Locally, Postgres runs in Docker.

The permission rules stay as they are: every query keeps its filter in `agent/records.py`, and the agent's connection stays read-only apart from the emergency incident write.

## Alternatives considered

- **Keep SQLite for operational data, Postgres for the rest**: two databases to seed, back up, and keep in sync.
- **SQLite for everything, including the checkpointer**: simple locally, but not suited to a server that handles several users at once, and the playbook's later steps assume Postgres.

## Consequences

- Queries in `agent/records.py` change from SQLite to Postgres syntax, so the access-control evaluation must pass again before anything else is built on them.
- Running the app needs Docker for Postgres.
- The seed script and the evaluation's throwaway database move to Postgres.
- One database to back up when package C arrives.
