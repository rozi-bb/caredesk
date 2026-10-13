# CareDesk — Roadmap

| | |
|---|---|
| Last updated | 2026-10-13 |

The order of work. What each feature must do is in [prd.md](prd.md); how it is built is in [architecture.md](architecture.md). Step numbers refer to the project's development playbook.

Legend: ✅ done · 🔄 in progress · ⬜ not started

## Release 1 — agent only, read-only

### Setup (once)

| # | Step | Status |
|---|---|---|
| 1 | Scaffold from the LangGraph template | ✅ |
| 2 | Git, `.gitignore`, `.env` | ✅ |
| 3 | `AGENTS.md` | ✅ |
| 4 | PRD | ✅ |
| 5 | Architecture | ✅ draft |
| 6 | Roadmap | ✅ |
| 6a | Push to a private GitHub repository, so history is backed up and visible from the planning stage | ✅ |
| 6b | Write ADRs for the decisions already made ([adr/](adr/)) | ✅ |
| 7 | Turn on tracing and confirm traces reach LangSmith | ✅ |
| 8 | Run the baseline graph in Studio | ✅ |
| 8a | Prepare data: operational seed script and DB | ✅ |

### Features (one at a time, each evaluated before the next)

Each feature is one loop of build (step 9) → evaluate (step 17). If the evaluation fails, fix before moving on. Each loop ends with a short note in `docs/iterations/` and an ADR for every decision made along the way.

| # | Feature | PRD | Done when | Status |
|---|---|---|---|---|
| 9.1 | Conversation memory | F1 | The assistant answers from earlier turns in Studio, and still does after the server restarts | ✅ [note](iterations/9.1-conversation-memory.md) |
| 9.2 | Read tools with access control | F2 | Permission filters pass unit tests; access-control evaluation is 100% | ✅ [note](iterations/9.2-read-tools-access-control.md) |
| 9.3 | Rules search with citations | F3 | F-tags chosen, handbook written, index built; first groundedness baseline recorded | ✅ [note](iterations/9.3-rules-search-citations.md) |
| 9.4 | Emergency triage and clinical decline | F4, F5 | Safety evaluation is 100% | ✅ [note](iterations/9.4-triage-and-guardrails.md) |

Decisions made along the way: embeddings and vector store in 9.3 (ADR-0015), emergency keyword pre-check in 9.4 (ADR-0016). Still open: the evaluation judge, needed before the first LLM-as-judge run (architecture.md, "Open decisions").

### Release

| Step | Status |
|---|---|
| Full evaluation across all four categories in prd.md section 8 | ✅ |
| Set targets for correctness and groundedness from the baseline | ✅ [ADR-0018](adr/0018-release-targets.md) |
| Update README with a short demo | ✅ |
| Tag `v0.1.0` | ✅ [note](iterations/release-1.md) |

## Release 2 — thin app, local

Playbook stage 2, without deployment: the release 1 agent behind our own backend, with sign-in and a chat UI, running locally ([ADR-0019](adr/0019-release-2-thin-local-app.md)). The four evaluations run again in each package.

### Package A — backend

| # | Step | Status |
|---|---|---|
| 10 | Backend skeleton: FastAPI with a health check, calls the agent, reads config and secrets from the environment ([ADR-0020](adr/0020-own-backend-not-agent-server.md)) | ✅ |
| 11 | Postgres in Docker: operational data moved from SQLite, accounts, usage, conversation memory; schema changes as migration files ([ADR-0021](adr/0021-one-postgres-database.md)) | ✅ |
| 12 | Sign-in with accounts created by the home; users open only their own threads ([ADR-0022](adr/0022-accounts-created-by-the-home.md)) | ✅ |
| 13 | Chat endpoint: check sign-in, call the agent, record usage, stream the answer | ✅ |
| 18 | Business-flow tests: sign-in, wrong password, usage recorded | ✅ |
| 19 | Security tests: thread isolation, no endpoint without sign-in, prompt injection | ✅ |

Package A note: [iterations/r2-a-backend.md](iterations/r2-a-backend.md).

### Package B — UI

| # | Step | Status |
|---|---|---|
| 16 | Chat UI in the browser with Chainlit, as a client of the backend ([ADR-0024](adr/0024-chainlit-ui-as-backend-client.md)) | ✅ |
| 19 | Security tests: the API key never reaches the browser | ✅ |

Package B note: [iterations/r2-b-ui.md](iterations/r2-b-ui.md).

Still open: rate limiting, which must never block an emergency message (prd.md section 10). Needed before the app is reachable by others, so it moves to package C.

Not planned: packages and usage limits (step 14) and payments (step 15). CareDesk serves one home that pays per use, and a hard limit could block an emergency ([ADR-0009](adr/0009-no-hard-usage-limits.md)).

## Package C — deploy and monitor

After release 2, when the app needs to be online.

| # | Step |
|---|---|
| 20 | VPS, domain, HTTPS; Docker Compose behind Nginx |
| 21 | Separate production keys and environment |
| 22 | Scheduled database backups, with a tested restore |
| 23 | Release procedure: tag, backup, deploy, migrate, smoke check, rollback plan |
| 24 | Quality monitoring: traces, Insights, user feedback |
| 25 | Cost per user from trace metadata and usage records |
| 26 | Error and uptime monitoring; spending alert at the model provider |

## Later

Not ordered yet. The order is decided after release 2, based on what monitoring and users show.

- Resident access
- Write actions with human confirmation, and data entry forms
- LLM-as-judge and human review in evaluation (step 17); the judge must come from another provider ([ADR-0010](adr/0010-judge-from-a-different-provider.md))
- More evaluation cases from the playbook checklist: out-of-scope questions, prompt injection, system-prompt leaks, answer relevance
