# ADR-0016: A narrow keyword check before the triage model

- Status: Accepted
- Date: 2026-10-03

## Context

ADR-0006 left open whether some emergencies should be caught before the triage model is called. A model call adds latency and can fail; for "she's not breathing" neither is acceptable.

## Decision

Before the model, a regular expression matches a short list of unmistakable, present-tense emergency phrases: not breathing, can't breathe, chest pain, unconscious, unresponsive, not waking up, choking, heavy bleeding, "just fell", "has fallen", "can't get up", fire, smoke. A match goes straight to the emergency path with no model call. Everything else goes to the model.

The list is deliberately narrow. Words like "fall" or "fire" alone are not on it, because staff ask administrative questions such as "which incidents involving a fall need action?" or "what is the fire evacuation procedure?", and a false alarm also writes an incident record.

## Alternatives considered

- **Model only**: every emergency waits for, and depends on, a model call.
- **Broad keyword list** ("fall", "fire", "pain"): many false alarms on everyday questions, each creating an incident record.

## Consequences

- The most obvious emergencies work even when the model provider is down.
- Unit tests pin both directions: emergency phrases match, look-alike admin questions do not.
- Anything subtler (sudden confusion, a drooping face, a missing resident) relies on the model, which is measured by the safety evaluation.
