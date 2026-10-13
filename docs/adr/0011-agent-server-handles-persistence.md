# ADR-0011: The Agent Server handles conversation persistence

- Status: Accepted, verified in feature 9.1 (memory survived a server restart; see [iteration note](../iterations/9.1-conversation-memory.md))
- Superseded by [ADR-0020](0020-own-backend-not-agent-server.md) for the app from release 2; still applies to development in Studio
- Date: 2026-10-03

## Context

LangGraph's official documentation says that when a graph runs on the Agent Server, checkpointers and stores are managed by the server and do not need to be configured in code. Release 1 always runs on the server (`langgraph dev`).

## Decision

Do not compile the graph with a checkpointer. Rely on the server for per-thread state, and use `thread_id` to separate conversations.

## Alternatives considered

- **Configure our own SQLite checkpointer in code**: needed only when running the graph outside the server, and duplicates what the server does.
- **A custom checkpointer through `langgraph.json`**: possible later if we need control over storage.

## Consequences

- Less code, and the same graph file works locally and when deployed.
- Behavior depends on the server. Feature 9.1 must prove that memory survives a server restart; if it does not, this decision is revisited.
- Postgres-backed persistence arrives with the backend (playbook step 11).
