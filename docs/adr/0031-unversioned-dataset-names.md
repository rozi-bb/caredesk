# ADR-0031: Evaluation datasets have no version in their name

- Status: Accepted
- Date: 2026-10-16

## Context

ADR-0014 put a version in each dataset name (`caredesk-safety-v3`), so changing the examples created a new dataset and old experiments stayed next to the data they ran on. After several bumps the LangSmith workspace held old versions nobody used, and the owner reset every CareDesk dataset to start clean.

## Decision

Datasets are named by suite only: `caredesk-access-control`, `caredesk-correctness`, `caredesk-groundedness`, `caredesk-safety`. The runner still creates a dataset only when no dataset with that name exists.

## Alternatives considered

- **Keep versioned names**: old experiments stay comparable, but old datasets pile up and must be cleaned by hand anyway.
- **Sync examples into the existing dataset on every run**: no manual step, but rewriting examples under existing experiments makes those experiments compare against data they did not run on.

## Consequences

- When the cases in `evals/suites.py` change, delete that dataset in LangSmith before the next run. Otherwise the run uses the old examples.
- Experiments from before a change are not kept next to the new examples, so a change cannot be compared against earlier runs in the LangSmith comparison view.
