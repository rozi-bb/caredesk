# ADR-0014: Code-based evaluators in release 1

- Status: Accepted. Versioned dataset names superseded by [ADR-0031](0031-unversioned-dataset-names.md)
- Date: 2026-10-03

## Context

ADR-0010 requires the LLM judge to come from a different provider than DeepSeek. The second provider (OpenAI) has no credit, so no LLM judge can run yet. The release 1 categories in prd.md section 8 can still be checked precisely, because the data is synthetic and the answers are known.

## Decision

All release 1 evaluations use code-based evaluators in LangSmith:

| Category | Check |
|---|---|
| Access control | No tool returned another resident's records; the answer contains none of the listed protected facts |
| Correctness | Each expected fact appears in the answer, in one of its accepted forms |
| Groundedness | Cited sources exist in what the search tool returned |
| Safety | The message took the expected route; emergencies created an incident record |

Datasets are versioned by name (`caredesk-access-control-v1`). Changing the examples means a new version, so earlier experiments stay comparable to the data they ran on. Each run uses a freshly seeded throwaway database.

## Alternatives considered

- **LLM judge from the same provider**: rejected in ADR-0010.
- **Wait for a second provider**: blocks evaluation of every feature.

## Consequences

- Evaluations are cheap, fast, and deterministic in their scoring.
- String checks can fail a correct answer phrased in an unexpected way, so failures are read by hand before anything is changed.
- Tone and helpfulness are not measured until an LLM judge is added.
