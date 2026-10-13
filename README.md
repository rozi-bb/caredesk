# CareDesk

An administrative assistant for a fictional nursing home, built with LangGraph. It answers staff and family questions from the home's data and from federal nursing-home regulations, cites its sources, and declines anything medical.

**Status:** release 1 features are built and evaluated; the release step (targets, demo, tag) is next. The agent runs locally in LangGraph Studio; there is no end-user app yet.

## Getting started

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Create your environment file and fill in the keys:

   ```bash
   cp .env.example .env
   ```

   You need a LangSmith API key and a DeepSeek API key.

3. Build the sample database (synthetic data, rebuilt identically every time):

   ```bash
   uv run python scripts/seed_db.py
   ```

4. Build the rules search index (downloads a small local embedding model the first time):

   ```bash
   uv run python scripts/build_rules_index.py
   ```

5. Start the local server and open Studio:

   ```bash
   uv run langgraph dev
   ```

## Evaluation

Runs the evaluation suites in LangSmith against a freshly seeded copy of the database:

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
