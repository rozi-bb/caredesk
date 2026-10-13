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

Decisions made along the way: embeddings and vector store in 9.3 (ADR-0015), emergency keyword pre-check in 9.4 (ADR-0016). Still open: the evaluation judge, needed before the first LLM-as-judge run (architecture.md section 9).

### Release

| Step | Status |
|---|---|
| Full evaluation across all four categories in prd.md section 8 | ✅ |
| Set targets for correctness and groundedness from the baseline | ✅ [ADR-0018](adr/0018-release-targets.md) |
| Update README with a short demo | ✅ |
| Tag `v0.1.0` | ✅ [note](iterations/release-1.md) |

## Release 2 — thin version, end to end

Playbook stage 2: a thin version that runs end to end and is used by a few people. Scope is confirmed in prd.md before work starts.

| # | Step | Status |
|---|---|---|
| 10 | Backend skeleton: server with a health check, calls the agent, reads config and secrets from the environment | ⬜ |
| 11 | Postgres: users, usage history (one row per event), conversation memory; schema changes as migration files | ⬜ |
| 12 | Login: every request carries the user, and users can open only their own threads | ⬜ |
| 13 | Chat endpoint: check login, call the agent, record usage, stream the answer | ⬜ |
| 16 | End-user UI, Chainlit as the candidate | ⬜ |
| 18 | Business-flow tests: sign-up and login | ⬜ |
| 19 | Security tests: thread isolation, no API key in the frontend, no endpoint without login, rate limiting, prompt injection | ⬜ |
| 20 | VPS, domain, HTTPS; Docker Compose behind Nginx | ⬜ |
| 21 | Separate production keys and environment | ⬜ |
| 22 | Scheduled database backups, with a tested restore | ⬜ |
| 23 | Release procedure: tag, backup, deploy, migrate, smoke check, rollback plan | ⬜ |
| 24 | Quality monitoring: traces, Insights, user feedback | ⬜ |
| 25 | Cost per user from trace metadata | ⬜ |
| 26 | Error and uptime monitoring; spending alert at the model provider | ⬜ |

Open before step 19: rate limiting must not block an emergency message ([ADR-0009](adr/0009-no-hard-usage-limits.md)).

Not planned: packages and usage limits (step 14) and payments (step 15). CareDesk serves one home that pays per use, and a hard limit could block an emergency ([ADR-0009](adr/0009-no-hard-usage-limits.md)).

## Later

Not ordered yet. The order is decided after release 2, based on what monitoring and users show.

- Resident access
- Write actions with human confirmation, and data entry forms
- LLM-as-judge and human review in evaluation (step 17); the judge must come from another provider ([ADR-0010](adr/0010-judge-from-a-different-provider.md))
- More evaluation cases from the playbook checklist: out-of-scope questions, prompt injection, system-prompt leaks, answer relevance
