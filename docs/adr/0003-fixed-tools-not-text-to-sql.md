# ADR-0003: Fixed tools instead of text-to-SQL

- Status: Accepted
- Date: 2026-09-30

## Context

Natural-language query, where the model writes SQL itself, is the flexible way to answer data questions. It conflicts with ADR-0002: a model-written query can reach rows the caller may not see.

## Decision

The model calls a fixed set of parameterized tools and never writes queries. The queries are written by developers and contain the permission filter.

## Alternatives considered

- **Text-to-SQL on a read-only connection**: flexible, but row-level permissions are hard to guarantee, and a wrong query silently returns wrong rows.
- **Text-to-SQL over per-role views**: workable, but it still relies on the model writing correct queries and adds database complexity.

## Consequences

- Questions outside the tools' scope cannot be answered, and the assistant says it does not know.
- New capability means a new tool.
- Tools are deterministic and unit-testable.
- Revisit if analytics-style questions become common.
