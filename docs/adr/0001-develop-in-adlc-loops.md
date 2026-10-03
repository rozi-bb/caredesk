# ADR-0001: Develop in ADLC loops from a written playbook

- Status: Accepted
- Date: 2026-09-30

## Context

An LLM agent does not fail in ways we can list in advance, so tests written up front miss the real failures. The project owner must also be able to explain every step of how the system was built.

## Decision

Follow LangChain's Agent Development Lifecycle (Build, Test/Evaluate, Deploy, Monitor) through the owner's written 25-step playbook.

- Plan before code: PRD, architecture, and roadmap exist before the first feature.
- One small loop per feature: build one feature, then evaluate it (steps 9 to 16). A failing evaluation is fixed before the next feature starts.
- Deploy once per release, not per feature.
- Evaluations are written from failures found by reading real outputs (error analysis), not from failures imagined in advance.

## Alternatives considered

- **Vibe coding** (prompt an AI for the whole app and accept the result): fast, but nobody can explain the result, and it fails the project's purpose.
- **Classic waterfall SDLC**: fixed phases with tests written from imagined failures.
- **Evaluation-first** (write evaluators before building): LLM failures cannot be anticipated, so the evaluators would test the wrong things.

## Consequences

- More writing before the first line of code.
- Every feature has an evaluation gate; nothing is stacked on an unevaluated feature.
- Decisions are recorded as they are made, in this folder.
