# ADR-0006: Triage first, fixed responses, fail toward emergency

- Status: Accepted. The keyword pre-check left open below was decided in [ADR-0016](0016-emergency-keyword-precheck.md). "If triage errors or times out, the message is treated as an emergency" is superseded by [ADR-0029](0029-jev-triage-with-deepseek-fallback.md), and the incident record by [ADR-0030](0030-emergencies-are-not-recorded.md); triage first and fixed responses still hold
- Date: 2026-10-03

## Context

A message like "I fell" must never be answered like an administrative question, and clinical questions must be declined every time. See architecture.md section 2 for the graph.

## Decision

- Every message goes through a triage node before anything else.
- The emergency and clinical-decline paths return fixed text and do not depend on a model choosing to say the right thing. The emergency path also writes an incident record.
- If triage errors or times out, the message is treated as an emergency.

## Alternatives considered

- **Put the rules in the agent's system prompt**: the model could skip them, especially after a long conversation.
- **Fail toward a normal answer**: a triage outage would silently remove the safety net.
- **Let the model write emergency instructions**: wording could drift or be wrong.

## Consequences

- Showing emergency contacts by mistake is cheap; missing an emergency is not.
- Triage adds one model call to every message.
- Safety evaluation must pass at 100%.
- Still open: whether a keyword check should run before the triage model (architecture.md section 9).
