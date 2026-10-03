# ADR-0010: Evaluation judge from a different provider

- Status: Accepted (judge model not chosen yet)
- Date: 2026-09-16

## Context

An LLM judge tends to rate answers that resemble its own style more highly (self-preference bias). If the same model answers and judges, scores look better than the real quality.

## Decision

The judge model must come from a different provider than the model that answers. The answering model is DeepSeek, so the judge is from another provider. The specific model is chosen when the first LLM-as-judge evaluation is built.

## Alternatives considered

- **Same model as judge**: simplest, but biased.
- **Same provider, different model**: reduces but does not remove the bias.
- **Human review only**: does not scale to repeated runs.

## Consequences

- A second provider account is needed (OpenAI, whose credit is currently empty, is one candidate).
- Judge prompts and a sample of judgments are still checked by a human.
