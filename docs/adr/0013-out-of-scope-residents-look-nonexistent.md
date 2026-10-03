# ADR-0013: Residents outside the user's scope look nonexistent

- Status: Accepted
- Date: 2026-10-03

## Context

If the assistant answered "You cannot see Dorothy Hale's records" for a real resident but "No such resident" for a made-up name, a family member could use it to find out who lives in the home.

## Decision

Name lookups only search residents the user may see. A resident outside that set gets exactly the same reply as a name that does not exist: "No resident you have access to matches '...'". Spelling suggestions are drawn only from the visible set. Billing is the one place where "no permission" is said explicitly, because the user is already linked to that resident.

## Alternatives considered

- **Say "you do not have permission" for any real resident**: confirms that the person lives here.
- **Refuse all name lookups for family**: family members would have to rely on "my resident" only, and could not name the right one when linked to two.

## Consequences

- Unit tests assert that an unlinked resident and a nonexistent name produce identical text.
- Staff, who may see everyone, get suggestions across all residents.
