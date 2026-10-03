# CareDesk

An administrative assistant for a fictional nursing home, built with LangGraph. It answers staff and family questions from the home's data and from federal nursing-home regulations, cites its sources, and declines anything medical.

**Status:** release 1 in progress. The agent runs locally in LangGraph Studio; there is no end-user app yet.

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

3. Start the local server and open Studio:

   ```bash
   uv run langgraph dev
   ```

## Documentation

| Document | What it covers |
|---|---|
| [Product requirements](docs/prd.md) | What CareDesk does, for whom, and its rules |
| [Architecture](docs/architecture.md) | How it is built |
| [Roadmap](docs/roadmap.md) | Order of work |
| [Decision records](docs/adr/) | Why each decision was made |

## Data

All resident, family, and staff data in this project is synthetic. Regulation text comes from the CMS State Operations Manual, Appendix PP, which is in the public domain.
