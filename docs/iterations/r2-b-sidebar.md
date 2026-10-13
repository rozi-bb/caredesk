# Release 2, package B follow-up — Private chat history in the sidebar

| | |
|---|---|
| Scope | PRD F8, [ADR-0025](../adr/0025-sidebar-history-from-the-backend.md) |
| Date | 2026-10-13 |
| Result | Done |

## Why

After `v0.2.0` the project owner noticed the sidebar of past conversations was missing. ADR-0024 had skipped Chainlit's data layer, and the sidebar went with it, without the owner being asked. The owner's requirement: like a normal chat app, users sign in, see their own past conversations, and continue them; nobody else can ever see them.

Lesson: a technical decision that removes something users see is a product decision, and must be asked first.

## Build

- **Backend**: `POST /threads` accepts an id chosen by the client, refused with 409 if any thread already has it. New `DELETE /threads/{id}` checks ownership, deletes the messages from the checkpointer and the thread row. Migration 0004 keeps usage rows when their thread is deleted.
- **UI**: `src/ui/data_layer.py`, a Chainlit data layer that stores nothing. It lists threads with the signed-in user's token, learns each thread's owner only from the backend, and treats any other thread as not found. The backend thread uses Chainlit's own thread id, so the sidebar and the backend agree.
- The "continue" buttons from package B are gone; the sidebar replaces them.
- The backend token is no longer returned to the page: the data layer keeps it in the UI process and returns the user without it.

## Test

| Check | How | Result |
|---|---|---|
| A chosen id can never take over a thread | Anne creates a thread with Peter's id | 409; Peter's thread unchanged |
| Only the owner can delete | Anne deletes Peter's thread, then Peter deletes it | 404, then 204; gone from list and history; usage kept |
| Sidebar lists only the user's own threads | Data layer with Peter and Anne signed in | Each sees only their own; an unknown user sees none |
| Unknown owner means not found | Thread not yet confirmed by the backend | No author, no content |
| Token not handed back to the page | `create_user` result | No token in it |
| All unit tests | | 76 passed |
| In the browser | Signed in as Peter: sidebar shows his conversations even after a UI restart; opened one and asked what the first question was. Logged out, signed in as Anne: empty sidebar; Peter's thread link refused (API 401); Anne's new chat appeared in her sidebar | All as expected |

## Error analysis

| Finding | What happened | Fix |
|---|---|---|
| Importing Chainlit in tests created `.chainlit/` and `.files/` in the project root | Chainlit creates its folders in the working directory on import | Tests point Chainlit at `src/ui` and its example env file |
| Thumbs up and down appeared under answers | Chainlit shows feedback buttons whenever a data layer exists | Not stored yet; open product question for the owner |

## Carried forward

- Decide whether to keep the feedback buttons (and store the feedback, for example in LangSmith) or hide them.
