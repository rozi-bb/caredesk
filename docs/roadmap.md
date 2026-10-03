# CareDesk — Roadmap

| | |
|---|---|
| Last updated | 2026-10-03 |

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
| 6a | Push to a private GitHub repository, so history is backed up and visible from the planning stage | 🔄 |
| 7 | Turn on tracing and confirm traces reach LangSmith | ⬜ |
| 8 | Run the baseline graph in Studio | ⬜ |
| 8a | Prepare data: operational seed script and DB | ⬜ |

### Features (one at a time, each evaluated before the next)

Each feature is one loop of build (step 9) → evaluate (step 16). If the evaluation fails, fix before moving on. Each loop ends with a short note in `docs/iterations/`.

| # | Feature | PRD | Done when | Status |
|---|---|---|---|---|
| 9.1 | Conversation memory | F1 | The assistant answers from earlier turns in Studio, and still does after the server restarts | ⬜ |
| 9.2 | Read tools with access control | F2 | Permission filters pass unit tests; access-control evaluation is 100% | ⬜ |
| 9.3 | Rules search with citations | F3 | F-tags chosen, handbook written, index built; first groundedness baseline recorded | ⬜ |
| 9.4 | Emergency triage and clinical decline | F4, F5 | Safety evaluation is 100% | ⬜ |

Decisions due along the way (see architecture.md section 9): embedding model and vector store before 9.3, emergency keyword pre-check before 9.4, evaluation judge before the first LLM-as-judge run.

### Release

| Step | Status |
|---|---|
| Full evaluation across all four categories in prd.md section 8 | ⬜ |
| Set targets for correctness and groundedness from the baseline | ⬜ |
| Update README with a short demo | ⬜ |
| Tag `v0.1.0` | ⬜ |

## After release 1

Not ordered yet. The order is decided when release 1 ships, based on what monitoring shows.

- Backend API and Postgres (playbook steps 10–11)
- Login (step 12)
- End-user UI, Chainlit as the candidate (step 15)
- Resident access
- Write actions with human confirmation, and data entry forms
- Per-user cost monitoring and spending alerts (steps 24–25)
- Business-flow and security tests (steps 17–18)
- Deployment to a VPS with backups (steps 19–22)
