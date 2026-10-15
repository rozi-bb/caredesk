# ADR-0017: Emergency records never block the emergency response

- Status: Superseded by [ADR-0030](0030-emergencies-are-not-recorded.md): emergencies are no longer recorded
- Date: 2026-10-03

## Context

The emergency path must write an incident record (prd.md F4). Two things can go wrong: the resident cannot always be identified from a chat message, and the database write itself can fail.

## Decision

- `incidents.resident_id` may be NULL. A family member linked to exactly one resident gets that resident filled in; otherwise it stays empty. A staff sender is recorded as the reporter. The message text, the sender's role, and id are stored in the description.
- The write uses its own connection in `rw` mode, so a missing database raises an error instead of silently creating an empty one.
- If the write fails, the user still gets the full emergency instructions, with a line asking them to tell a staff member directly instead of saying the message was recorded.
- The instructions and contacts are fixed text, matching the handbook: call bell or nearest staff, nurse station extension 200 (24 hours), and 911 if a life is in danger.

## Alternatives considered

- **Require a resident before recording**: would mean asking questions during an emergency.
- **Fail the run if the write fails**: the user would see an error instead of instructions.

## Consequences

- Staff must check open emergency records that have no resident attached.
- The assistant never claims the message was recorded when it was not.
