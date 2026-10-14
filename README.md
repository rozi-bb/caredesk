# CareDesk

An administrative assistant for a fictional nursing home, built with LangGraph. It answers staff and family questions from the home's data and from federal nursing-home regulations, cites its sources, and declines anything medical.

**Status:** release 1 (`v0.1.0`) is a read-only agent for staff and family. Release 2 wraps it into an app: staff and family sign in and chat in the browser. Everything runs locally.

## Demo

Real answers from the agent, shortened. The caller's identity comes from the run context, not from the chat.

**Staff member** asks about a resident:

> **Q:** What's on Mary Johnson's schedule today?
> **A:** Here is Mary Johnson's (room 114) schedule for today, Monday 05 October 2026: 08:00 morning medication round, 08:30 personal care, 12:00 lunch assistance, 19:00 personal care, 20:00 evening medication round.

**Family member** (Peter, son of Harold Bennett) asks the same question. Residents outside their access look as if they do not exist:

> **Q:** What's on Mary Johnson's schedule today?
> **A:** I'm sorry, but I don't have access to any resident named Mary Johnson. The record I can see for you is linked to Harold Bennett (room 210). Would you like me to look up Harold's schedule for today instead?

A rules question, answered with citations:

> **Q:** Can I visit my father in the evening?
> **A:** Yes, you can. Residents may receive visitors at any time of day, and family members have immediate access, subject to the resident's right to decline a visit [Handbook: Visiting]. Family members are not subject to visiting-hour limits, apart from reasonable clinical or safety restrictions [F563].

An emergency gets fixed instructions and an incident record, with no model writing the reply:

> **Q:** My father isn't waking up!
> **A:** This sounds like an emergency. If someone is in danger right now: press the call bell or alert the nearest staff member; call the nurse station on extension 200 (staffed 24 hours); if someone's life is in danger, call 911. I have recorded your message for the nursing team to follow up.

A medical question is declined:

> **Q:** Should my father take an extra dose of his blood pressure pill?
> **A:** I can't give medical advice, diagnoses, or guidance about medication or treatment. Please speak to the nursing staff at the nurse station (extension 200, staffed 24 hours).

More questions to try are in [docs/manual-testing.md](docs/manual-testing.md).

## Getting started

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and Docker.

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Create your environment file and fill in the keys:

   ```bash
   cp .env.example .env
   ```

   You need a LangSmith API key, a DeepSeek API key, and an `AUTH_SECRET` (the file says how to generate one).

3. Start Postgres:

   ```bash
   docker compose up -d
   ```

4. Build the sample database (synthetic data, rebuilt identically every time). This also creates an account for every staff and family member, with random demo passwords written to `data/demo_accounts.csv`:

   ```bash
   uv run python scripts/seed_db.py
   ```

5. Build the rules search index (downloads a small local embedding model the first time):

   ```bash
   uv run python scripts/build_rules_index.py
   ```

6. Start the backend (keep it running):

   ```bash
   uv run uvicorn backend.main:app --env-file .env
   ```

7. In a second terminal, set up and start the chat UI. It has its own environment file, with only the backend's address and a session secret:

   ```bash
   cp src/ui/.env.example src/ui/.env
   ```

   ```bash
   uv run chainlit create-secret
   ```

   Put the secret in `src/ui/.env` as `CHAINLIT_AUTH_SECRET`, then:

   ```bash
   cd src/ui && uv run chainlit run app.py --port 8001
   ```

   Open http://localhost:8001 and sign in with an email and password from `data/demo_accounts.csv`.

8. Optional: chat from Telegram too. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`; `/setjoingroups` → Disable). In the root `.env`, set `TELEGRAM_BOT_USERNAME` to the bot's username and `TELEGRAM_BOT_KEY` to a new random key, then restart the backend. The bot has its own environment file:

   ```bash
   cp src/telegram_bot/.env.example src/telegram_bot/.env
   ```

   Fill in the token from BotFather and the same `TELEGRAM_BOT_KEY`, then, in a third terminal:

   ```bash
   uv run --env-file src/telegram_bot/.env python -m telegram_bot
   ```

   In the chat UI, press **Connect Telegram** and open the link (or scan the QR code) on your phone. The bot fetches messages itself, so nothing needs to be reachable from the internet.

The backend's API can also be tried directly at http://127.0.0.1:8000/docs. For development, the graph runs in LangGraph Studio with the identity typed in by hand:

```bash
uv run langgraph dev
```

## Evaluation

Runs the evaluation suites in LangSmith against a freshly seeded throwaway database (Postgres must be running), and exits with an error if any suite misses its target (targets are in [prd.md](docs/prd.md) section 8):

```bash
uv run python -m evals.run
```

## Documentation

| Document | What it covers |
|---|---|
| [Product requirements](docs/prd.md) | What CareDesk does, for whom, and its rules |
| [Architecture](docs/architecture.md) | How it is built |
| [Roadmap](docs/roadmap.md) | Order of work |
| [Manual testing](docs/manual-testing.md) | Questions to try each feature in Studio |
| [Decision records](docs/adr/) | Why each decision was made |

## Data

All resident, family, and staff data in this project is synthetic. Regulation text in `corpus/ftags/` is extracted from the CMS State Operations Manual, Appendix PP, which is in the public domain (`scripts/extract_ftags.py` re-extracts it from the PDF). The handbook in `corpus/handbook.md` is fictional.
