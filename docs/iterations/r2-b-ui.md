# Release 2, package B — Chat UI

| | |
|---|---|
| Scope | Roadmap steps 16 and 19 (package B) |
| Date | 2026-10-13 |
| Result | Done |

## Build

- **Chainlit UI** in `src/ui/` ([ADR-0024](../adr/0024-chainlit-ui-as-backend-client.md)): sign-in through the backend, a greeting with emergency contacts, streamed answers, and buttons to continue up to five earlier conversations. `client.py` is the only way the UI reaches anything: plain HTTP calls to the backend with the user's token.
- **Thread titles**: migration 0003 adds a title, set from the first question, so earlier conversations can be recognised.
- **Separate UI environment**: `src/ui/.env` holds only `BACKEND_URL` and `CHAINLIT_AUTH_SECRET`.
- **Chainlit settings**: session length matches the backend token (8 hours); file upload, message editing, and the new-chat warning are off; only the local UI origin is allowed.

## Test

| Check | How | Result |
|---|---|---|
| UI's backend client | Against the real backend in process, fake models: sign-in, wrong password, streamed answer, thread list with titles, history, expired token, someone else's thread | Pass |
| UI cannot reach models or the database (step 19) | The UI's imports are checked; its env example may hold only the two allowed names | Pass |
| Keys never reach the browser (step 19) | Signed in as Peter and fetched everything a browser gets: the page, its JavaScript (4.6 MB), `/user`, settings, translations. Searched for the DeepSeek and LangSmith keys and the backend's signing secret | None found |
| All unit tests | | 69 passed |
| In the browser, real models | Signed in as Peter; schedule question; rules question with citations; emergency; new chat, continued the earlier conversation, asked what the first question was | All worked; memory carried over |

## Error analysis

| Finding | What happened | Fix |
|---|---|---|
| Chainlit would have loaded every backend key | Chainlit reads `.env` from the folder it runs in; from the project root that is the backend's file, model keys included | The UI runs from `src/ui/` with its own `.env` |
| Chainlit would have switched on its own database | Chainlit starts a data layer when it sees `DATABASE_URL`, which the backend's environment has | Same fix; a test keeps `DATABASE_URL` out of the UI's environment |
| The backend token is visible to the page | Chainlit keeps the user's metadata in its session and returns it on `/user` | Accepted and recorded in ADR-0024: it is the user's own 8-hour token; the keys check above passed |
| "This will clear your current chat history" on New chat | Chainlit's default warning; nothing is lost, the backend keeps every conversation | Warning switched off |
| Times on the continue buttons were 7 hours off | The backend sends UTC | Shown in local time |
| "Since your father has a roommate…" | Asked about evening visits, the agent applied F563's roommate rule as if Harold had a roommate. No tool says so, and rooms hold one resident. The groundedness checks did not catch it: they only check citation labels | Not fixed in this package. Recorded for the LLM judge, which can compare claims with tool output (ADR-0010) |
| The app's preview panel could not start the servers | As in package A, the process stopped while reading the project folder, most likely waiting for macOS folder permission | Verified with servers started from a terminal |

## Carried forward

- The roommate claim: a groundedness case for the LLM judge, and possibly a prompt rule about applying rules to a specific resident.
- Rate limiting, before the app is reachable by others (package C).
- Package C: deployment and monitoring.
