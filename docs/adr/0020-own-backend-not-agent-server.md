# ADR-0020: Our own backend runs the graph, not the Agent Server

- Status: Accepted
- Date: 2026-10-13

## Context

In release 1 the LangGraph Agent Server (`langgraph dev`) runs the graph and stores conversations (ADR-0011). Release 2 needs login, private conversations, and storage that survives restarts. The Agent Server supports custom authentication and per-user thread ownership, but according to the official documentation:

- `langgraph dev` keeps state in memory and a local file, and is meant for development and testing.
- `langgraph up`, which stores state in Postgres, needs a license key for custom authentication.
- Self-hosting the Agent Server requires an Enterprise plan.

The project owner does not want to pay for LangSmith hosting or a license.

## Decision

A backend we write ourselves, with FastAPI, runs the graph. It compiles the graph with LangGraph's open-source Postgres checkpointer (`langgraph-checkpoint-postgres`) and owns login, thread ownership, streaming, and usage records.

`langgraph.json` and `langgraph dev` stay for development, so the graph can still be run and inspected in Studio.

## Alternatives considered

- **Agent Server with custom authentication**: less code, but deploying it (package C) needs paid LangSmith hosting or an Enterprise license.
- **The UI framework as the backend** (Chainlit calls the graph itself): fewer moving parts, but mixes UI and backend, and the API could not be tested without the UI.

## Consequences

- More code: thread ownership, streaming, and the chat endpoint are ours to write and test.
- Every layer is open source and can run on any server.
- `build_graph()` already accepts a `checkpointer`, so the graph itself does not change.
- [ADR-0011](0011-agent-server-handles-persistence.md) now applies only to development in Studio.
- LangSmith is still used for tracing and evaluation, which are separate from hosting.
