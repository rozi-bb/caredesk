# ADR-0024: The chat UI is a Chainlit app that only calls the backend

- Status: Accepted; history part superseded by [ADR-0025](0025-sidebar-history-from-the-backend.md)
- Date: 2026-10-13

## Context

Package B adds a chat UI in the browser. The project owner chose Chainlit, an open-source chat UI for Python. Chainlit can run the graph itself, keep its own history, and handle sign-in, but the backend already does all three (ADR-0020, ADR-0022). Model keys must never reach the browser (roadmap step 19).

## Decision

- The UI (`src/ui/`) is a client of the backend API. The browser talks only to Chainlit; Chainlit's server calls the backend with the signed-in user's token. The UI never imports the graph, a model, or the database, and a test checks this.
- Sign-in uses Chainlit's password form, checked by the backend's `/auth/login`. The backend token is kept in the Chainlit session, which lasts 8 hours like the token.
- Conversation history stays in the backend. There is no Chainlit data layer; earlier conversations are offered as buttons on a new chat, using the backend's thread list.
- The UI runs from `src/ui/` with its own `.env`, holding only `BACKEND_URL` and `CHAINLIT_AUTH_SECRET`. Chainlit loads `.env` from the folder it runs in, and switches on its own database if it sees `DATABASE_URL`, so the UI must not share the backend's environment file.

## Alternatives considered

- **Chainlit runs the graph directly**: rejected in ADR-0020; the API could not be tested without the UI.
- **Chainlit's data layer for history**: a second copy of every conversation, in tables we do not own.
- **A custom web frontend**: more work for the same result in a thin release.

## Consequences

- The browser can read the user's backend token (Chainlit returns the session user to the page). It is the user's own credential, valid for 8 hours; model keys and signing secrets were checked and never appear in anything the browser receives.
- Two processes and two env files to run locally: backend and UI.
- Editing a sent message is switched off, because the backend's conversation cannot be rewritten.
- Chainlit's sidebar history is not used; the UI shows up to five earlier conversations on each new chat.
