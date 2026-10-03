# ADR-0002: Enforce permissions in the tool layer, not in the prompt

- Status: Accepted
- Date: 2026-09-16

## Context

Staff and family members must see different data (see prd.md section 3). A system-prompt rule such as "never show other residents' data" can be argued around: a user can claim to be a doctor, or paste instructions that look authoritative.

## Decision

Authorization lives in the tools. Every operational tool filters by `role` and `user_id` from the graph's runtime context, inside its own query, before any row is returned. Identity comes from the runtime context, never from the conversation.

## Alternatives considered

- **Instruct the model in the system prompt**: depends on the model refusing every time, and prompt injection defeats it.
- **Filter the model's answer afterwards**: the data has already reached the model and can leak through paraphrase.
- **A separate agent per role**: still needs data-level filtering, and doubles what must be maintained.

## Consequences

- A manipulated model still cannot reveal data that no tool returned.
- Permission logic is ordinary code and can be unit-tested.
- The access-control evaluation attacks this directly and must pass at 100% (prd.md section 8).
- Every new tool must implement the filter. Forgetting it is the main risk, so it belongs in review.
