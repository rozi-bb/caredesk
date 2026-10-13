# ADR-0022: Email and password accounts, created by the home

- Status: Accepted
- Date: 2026-10-13

## Context

Release 2 replaces typed-in identity with real sign-in. In this product, an account decides which resident's data someone can see. If anyone could sign up and claim to be a resident's son, the permission rules would protect nothing.

## Decision

- Users sign in with email and password. Passwords are stored only as a one-way hash.
- There is no self sign-up. Every account is created by the home and linked to an existing staff or family record. In release 2 the seed script creates them; an admin screen comes later.
- After sign-in, `user_id` and `role` come from the account and are placed in the graph's runtime context, as in release 1. The tools do not change.

## Alternatives considered

- **Self sign-up**: anyone could claim a family link and see a resident's data.
- **Sign-in through an outside provider (Google, Supabase)**: depends on an outside service while everything else runs locally, and still needs the link to a staff or family record.
- **Magic links by email**: needs an email service, which is out of scope.

## Consequences

- Demo accounts and their passwords come from the seed script and are never committed.
- Password reset is handled by the home for now; reset by email is out of scope.
- The playbook's business-flow test "sign-up works" becomes "only accounts created by the home can sign in".
