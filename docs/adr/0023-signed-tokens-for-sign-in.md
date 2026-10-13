# ADR-0023: Signed tokens for sign-in

- Status: Accepted
- Date: 2026-10-13

## Context

After sign-in (ADR-0022), every request must carry proof of who is asking. The backend is a JSON API that a separate UI will call (package B), and it runs as a single process for now.

## Decision

Sign-in returns a signed token (a JWT, HS256) holding only the account id and an expiry, valid for 8 hours by default. The client sends it as `Authorization: Bearer <token>`. On every request the backend checks the signature and expiry, then loads the account from the database, so the role always comes from the database and never from the token or the request body.

The signing secret is `AUTH_SECRET`; the backend refuses to start without one of at least 32 characters.

## Alternatives considered

- **Server-side sessions** (a session table, a random id in a cookie): can be revoked instantly, but adds a table and a lookup per request, and cookies need CSRF protection once a browser UI exists.
- **Putting the role in the token**: saves a query, but a role change would not apply until the token expires.

## Consequences

- No logout on the server: a stolen token works until it expires. The short lifetime limits this; revocation, if needed, means adding a deny-list or switching to sessions.
- Rotating `AUTH_SECRET` signs everyone out.
- Wrong email and wrong password get the same reply and take the same time, so the sign-in endpoint does not reveal which emails have accounts.
