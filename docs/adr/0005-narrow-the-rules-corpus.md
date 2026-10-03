# ADR-0005: Narrow the rules corpus to selected F-tags

- Status: Accepted. Tag list chosen in feature 9.3 ([iteration note](../iterations/9.3-rules-search-citations.md))
- Date: 2026-09-16

## Context

Appendix PP is 926 pages covering about 200 F-tags. Most are clinical or about buildings and kitchens. Indexing all of it adds noise: a question about visiting hours can retrieve text about infection control.

## Decision

Index 12 to 15 F-tags covering resident rights, visiting and family notification, complaints, and restraint and abuse protection. Choose them from real example questions of each role: questions first, tags second. Clinical and building or fire-safety tags are left out on purpose.

## Alternatives considered

- **Ingest everything**: noisier retrieval and less precise citations.
- **Handbook only, no regulations**: nothing external to check citations against.

## Consequences

- Citations map to F-tag numbers, so citation accuracy can be checked by code.
- Areas left out are also areas the assistant must decline, so the corpus boundary and the guardrail boundary agree.
- Questions outside the corpus get "I don't know".
- The final list is chosen during feature 9.3 and recorded in the iteration note.
