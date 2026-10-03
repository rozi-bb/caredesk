# Architecture Decision Records

An ADR records one decision: the situation, what was chosen, what was rejected, and what it costs. [architecture.md](../architecture.md) says how the system is built; the ADRs say why.

Format: Status, Date, Context, Decision, Alternatives considered, Consequences. A decision is never edited after the fact. To change one, write a new ADR and mark the old one `Superseded by ADR-xxxx`.

| # | Decision | Status |
|---|---|---|
| [0001](0001-develop-in-adlc-loops.md) | Develop in ADLC loops from a written playbook | Accepted |
| [0002](0002-enforce-permissions-in-tools.md) | Enforce permissions in the tool layer, not in the prompt | Accepted |
| [0003](0003-fixed-tools-not-text-to-sql.md) | Fixed tools instead of text-to-SQL | Accepted |
| [0004](0004-synthetic-data-real-regulations.md) | Synthetic operational data, real regulations | Accepted |
| [0005](0005-narrow-the-rules-corpus.md) | Narrow the rules corpus to selected F-tags | Accepted |
| [0006](0006-triage-first-fail-safe.md) | Triage first, fixed responses, fail toward emergency | Accepted |
| [0007](0007-fixed-reference-date.md) | Fixed reference date for "today" | Accepted |
| [0008](0008-release-1-agent-only-read-only.md) | Release 1 is agent-only and read-only | Accepted |
| [0009](0009-no-hard-usage-limits.md) | No hard usage limits | Accepted |
| [0010](0010-judge-from-a-different-provider.md) | Evaluation judge from a different provider | Accepted |
| [0011](0011-agent-server-handles-persistence.md) | The Agent Server handles conversation persistence | Accepted, verified |
| [0012](0012-family-see-medication-round-times.md) | Family members see medication-round times | Accepted |
| [0013](0013-out-of-scope-residents-look-nonexistent.md) | Residents outside the user's scope look nonexistent | Accepted |
| [0014](0014-code-based-evaluators.md) | Code-based evaluators in release 1 | Accepted |
