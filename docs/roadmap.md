# CareDesk — Roadmap

| | |
|---|---|
| Last updated | 2026-10-16 |

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
| 16 | Follow-up: past conversations in the sidebar, private to each user ([ADR-0025](adr/0025-sidebar-history-from-the-backend.md)) | ✅ |

Package B notes: [iterations/r2-b-ui.md](iterations/r2-b-ui.md), [iterations/r2-b-sidebar.md](iterations/r2-b-sidebar.md).

Not planned: packages and usage limits (step 14) and payments (step 15). CareDesk serves one home that pays per use, and a hard limit could block an emergency ([ADR-0009](adr/0009-no-hard-usage-limits.md)).

## Package C — monitor, locally

CareDesk is a portfolio project and is never deployed ([ADR-0026](adr/0026-no-deployment.md)). Only cost per user is built, on the app running locally.

| # | Step | Status |
|---|---|---|
| 25 | Cost per user from trace metadata and usage records ([ADR-0033](adr/0033-cost-per-user-report.md)) | ✅ [note](iterations/cost-per-user.md) |

Not planned, because nothing is deployed: server, domain, and HTTPS (step 20), production keys (21), scheduled backups (22), the deploy procedure (23), uptime monitoring (26), and rate limiting, since only the owner can reach the app.

Not planned, because nobody else uses the app ([ADR-0032](adr/0032-no-quality-or-error-monitoring.md)): quality monitoring with Insights and user feedback (step 24), and error monitoring with a spending alert (26). Errors still show in LangSmith traces, and the DeepSeek balance is prepaid.

## Telegram channel

Staff and family can also chat with CareDesk from Telegram. Telegram is one more client of the backend, like the Chainlit UI; the agent does not change. The bot fetches messages itself (polling), so it runs locally without a public address. Requirements: prd.md F11–F15; design: [ADR-0027](adr/0027-telegram-as-a-backend-client.md).

| # | Step | Status |
|---|---|---|
| T1 | Create the bot with @BotFather; the bot token and the bot's backend key live only in `.env` | ✅ |
| T2 | Backend: links and one-time codes tables, connect and disconnect endpoints, chat endpoint for the bot, channel in usage | ✅ |
| T3 | Chainlit: Connect Telegram, the connected account's status, Disconnect | ✅ |
| T4 | Bot adapter: passes messages on, `/new`, `/disconnect`, private chats only, connect instructions and emergency contacts for unlinked users | ✅ |
| T5 | Fixed texts (greeting, emergency contacts) served by the backend, so Chainlit and the bot keep no copies of their own | ✅ |
| T6 | Stream answers in Telegram as they are written, with Telegram's message drafts ([ADR-0028](adr/0028-telegram-answers-stream-as-drafts.md)) | ✅ |
| 18 | Business-flow tests for Telegram (prd.md section 8) | ✅ |
| 19 | Security tests for Telegram (prd.md section 8) | ✅ |
| 17 | Run the four evaluations again to catch regressions | ✅ |
| — | Try it in real Telegram; update the README and `manual-testing.md`; write the iteration note | ✅ [note](iterations/telegram.md) |

Bot settings stay in `.env`; there is no admin settings page, because one home with one bot does not need one.

## Triage with Jev

Triage moves from the keyword check and DeepSeek classifier to Jev, with DeepSeek as the fallback and a fixed reply when both fail. Requirements: prd.md F16–F17; design: [ADR-0029](adr/0029-jev-triage-with-deepseek-fallback.md). The graph was not changed until step J3 showed Jev was good enough.

| # | Step | Status |
|---|---|---|
| J1 | `TYPESAFE_API_KEY` in the backend `.env` only; `.env.example` updated | ✅ |
| J2 | Connection test: one small decision call; check the key, the response format (`choice`, `probabilities`, `confidence`), and the response time | ✅ key and format as documented; one cold call took 2.7 s, so speed is measured properly in J3 |
| J3 | Compare Jev and DeepSeek on the safety cases, plus look-alike ordinary messages, without changing the graph: accuracy, speed, cost. Choose the emergency threshold X | ✅ X = 0.3; Jev as accurate as DeepSeek and about five times faster |
| J4 | Change triage: Jev, then DeepSeek, then the fixed `triage_unavailable` reply; remove the keyword check; trace which classifier decided | ✅ |
| 18 | Unit tests for the three paths: Jev decides, DeepSeek decides, both fail | ✅ |
| 17 | Run the four evaluations again; safety must be 100% | ✅ all four pass; Jev decided all 29 safety cases |
| — | Accept ADR-0029 (supersede ADR-0016 and the fail-safe part of ADR-0006); update architecture, both diagrams, and `manual-testing.md`; write the iteration note | ✅ [note](iterations/jev-triage.md) |
| — | Emergencies no longer write an incident record; the agent is fully read-only ([ADR-0030](adr/0030-emergencies-are-not-recorded.md)) | ✅ |


## Later

Not ordered yet. The order is decided after release 2, based on what monitoring shows.

- WhatsApp channel, after Telegram. It needs a Meta Business account and a public address for its webhook
- Resident access
- Write actions with human confirmation, and data entry forms
- LLM-as-judge and human review in evaluation (step 17); the judge must come from another provider ([ADR-0010](adr/0010-judge-from-a-different-provider.md))
- More evaluation cases from the playbook checklist: out-of-scope questions, prompt injection, system-prompt leaks, answer relevance
