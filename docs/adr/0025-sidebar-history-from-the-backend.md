# ADR-0025: Sidebar history read from the backend

- Status: Accepted
- Date: 2026-10-13
- Supersedes the "no Chainlit data layer" part of [ADR-0024](0024-chainlit-ui-as-backend-client.md)

## Context

ADR-0024 skipped Chainlit's data layer so conversations would not be stored twice. That also removed Chainlit's sidebar of past conversations, which only appears with a data layer. The project owner considers the sidebar essential: users sign in again, see what they asked before, and continue. Each user's conversations must be private, visible only to that user when signed in.

## Decision

A custom Chainlit data layer (`src/ui/data_layer.py`) that stores nothing and reads everything from the backend:

- **Listing**: Chainlit always filters by the signed-in user; the data layer asks the backend with that user's own token, so the backend decides what is theirs.
- **Ownership**: a thread's owner is known only after the backend returned it with the owner's token. An unknown thread has no owner, which Chainlit treats as not found. Opening, resuming, or deleting someone else's thread is refused by Chainlit, and again by the backend.
- **Same id everywhere**: the UI creates the backend thread with Chainlit's own thread id. The backend accepts a chosen id only if no thread has it, so an existing thread can never be taken over.
- **Deleting** goes through a new backend endpoint that checks ownership and removes the messages; usage rows are kept for cost per user.
- **Tokens**: the data layer reports no stored users, so Chainlit passes its signed-in user, with the backend token from the signed session cookie, on every request. The token is kept in the UI process and no longer returned to the page.

## Alternatives considered

- **Chainlit's built-in SQL data layer**: every message stored twice (Chainlit's tables and LangGraph's checkpoints), which can drift apart.
- **Keep the "continue" buttons**: works, but not what users expect from a chat app.

## Consequences

- One source of truth for conversations, and the sidebar is always in sync with it.
- The UI learns tokens and owners in memory; after a UI restart they are picked up again from the session cookie and the next sidebar load.
- Chainlit shows thumbs up and down on answers once a data layer exists. They are not stored yet; whether to keep them is an open product question.
