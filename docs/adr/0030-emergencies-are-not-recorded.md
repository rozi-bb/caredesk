# ADR-0030: Emergencies get a fixed reply and are not recorded

- Status: Accepted. Supersedes [ADR-0017](0017-emergency-records-never-block.md) and the incident record in [ADR-0006](0006-triage-first-fail-safe.md)
- Date: 2026-10-15

## Context

Since release 1, an emergency message got the fixed emergency reply and also wrote a "needs action" incident record, so the nursing team could follow up (ADR-0006, ADR-0017).

Trying it showed the records were thin. A staff member's message named the resident ("Rosa Moreno is choking on her lunch"), but the record left the resident empty, because the code only fills it in for a family member linked to exactly one resident. Making records useful would mean reading names out of the message, a new feature. The owner chose to drop recording instead.

## Decision

- An emergency gets the fixed reply with the emergency contacts and nothing else. The line saying whether the message was recorded is gone.
- The assistant writes nothing to the home's records. `record_emergency()` and the writable database connection are removed, so every connection the agent opens is read-only.
- The seed script no longer creates an "automatic record" emergency incident. The draft is still generated and then dropped, so the random numbers behind all later synthetic data, and the expected answers in the evaluation datasets, do not change.
- The `incidents` table stays. Staff still read the seeded incidents (falls, complaints, missing belongings, behaviour) through `get_incidents`.
- The safety evaluation drops its `emergency_recorded` check; routing and the fixed reply are still 100%.

## Alternatives considered

- **Keep recording, as before**: records without the resident were of little use to the nursing team.
- **Fill in the resident from names in the message**: more useful records, but a new feature with its own mistakes, such as two residents with similar names.
- **Drop the `incidents` table too**: would also remove staff's incident questions (prd.md F2), which read the seeded incidents.

## Consequences

- The nursing team gets no automatic record of an emergency message. Reaching staff relies on the user using the contacts in the reply.
- The assistant is fully read-only: no code path in the agent writes to the database.
- The emergency reply no longer depends on the database at all.
- The `incidents` table still accepts the `emergency` category, which nothing writes any more. Removing it would need a migration and is left until the table changes for another reason.
