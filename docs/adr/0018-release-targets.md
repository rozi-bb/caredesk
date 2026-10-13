# ADR-0018: Release targets for correctness and groundedness

- Status: Accepted
- Date: 2026-10-13

## Context

prd.md section 8 left the correctness and groundedness targets open until a baseline existed. Before release 1, the full evaluation ran seven times. Correctness was 100% every time. Groundedness missed three times across those runs: two honest "I don't know" answers that the evaluator's phrase list did not recognise, and one answer that merged two sources into a single label. The details are in [the release note](../iterations/release-1.md). Model answers vary between runs, and the datasets are small: 10 correctness questions, 10 rules questions, 3 unanswerable ones.

## Decision

| Check | Target |
|---|---|
| Correctness (`answer_contains_facts`) | 90% |
| Right source cited (`cites_expected_source`) | 90% |
| No invented source (`citations_were_retrieved`) | 100% |
| Honest "I don't know" (`admits_unknown`) | 90% |

Safety and access control stay at 100%. The targets live in `evals/suites.py`, and `evals.run` fails when any suite misses one.

## Alternatives considered

- **100% everywhere**: on ten questions, one answer worded differently would block a release without any bug behind it.
- **Lower targets, such as 80%**: two misses in ten would pass silently, while the baseline shows the agent does better.

## Consequences

- One miss in ten passes; two do not. Every miss is still printed and should be read.
- An invented source has no tolerance, because it breaks the product rule against making things up (prd.md section 6).
- With 3 unanswerable questions, 90% still means all three must pass. The rule is kept uniform so it scales as the dataset grows.
- Targets are revisited when the datasets grow or an LLM judge replaces phrase matching (ADR-0010, ADR-0014).
