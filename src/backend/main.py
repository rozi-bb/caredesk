"""HTTP API for CareDesk: sign-in, conversations, and the chat endpoint.

Run locally with:
    uv run uvicorn backend.main:app --env-file .env

The graph is the same one Studio runs. Here it is compiled with a Postgres
checkpointer, and the caller's identity comes from their account (ADR-0020,
ADR-0022), never from the request body.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

from agent.context import Context
from agent.graph import build_graph
from backend import store
from backend.config import Settings
from backend.security import create_token, read_token, verify_password

log = logging.getLogger(__name__)

Graph = CompiledStateGraph[Any, Any, Any, Any]
GraphFactory = Callable[[AsyncPostgresSaver], Graph]

# Nodes whose reply is fixed text rather than streamed model tokens.
FIXED_REPLY_NODES = ("emergency_response", "decline_clinical")
ERROR_REPLY = "Something went wrong on our side. Please try again."


class LoginRequest(BaseModel):
    """Email and password for signing in."""

    email: str = Field(max_length=320)
    password: str = Field(max_length=200)


class TokenResponse(BaseModel):
    """A sign-in token to send as `Authorization: Bearer <token>`."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class Profile(BaseModel):
    """Who is signed in."""

    email: str
    role: str
    name: str


class ThreadOut(BaseModel):
    """A conversation. The title is its first question, once there is one."""

    thread_id: uuid.UUID
    created_at: datetime
    title: str | None = None


class ChatRequest(BaseModel):
    """One message from the user."""

    content: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    """One message in a conversation's history."""

    role: str
    content: str


TITLE_LENGTH = 60


def _title(content: str) -> str:
    """Shorten the first question into a one-line title."""
    line = " ".join(content.split())
    return (
        line if len(line) <= TITLE_LENGTH else line[: TITLE_LENGTH - 1].rstrip() + "…"
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


_bearer = HTTPBearer(auto_error=False)


def pool_of(request: Request) -> store.Pool:
    """Return the app's database pool."""
    pool: store.Pool = request.app.state.pool
    return pool


async def current_account(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> store.Account:
    """Return the signed-in account, or reject the request with 401."""
    cfg: Settings = request.app.state.settings
    account_id = (
        read_token(credentials.credentials, cfg.auth_secret) if credentials else None
    )
    account = (
        await store.get_account(pool_of(request), account_id) if account_id else None
    )
    if account is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sign in first.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return account


Signed = Annotated[store.Account, Depends(current_account)]


async def require_thread(
    request: Request, account: store.Account, thread_id: uuid.UUID
) -> None:
    """Reject the request unless the thread belongs to the account."""
    # Someone else's thread looks exactly like a missing one (as in ADR-0013).
    if not await store.owns_thread(pool_of(request), account.id, thread_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")


def create_app(
    graph_factory: GraphFactory | None = None, settings: Settings | None = None
) -> FastAPI:
    """Build the API. Tests pass a graph factory with fake models."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        cfg = settings or Settings.from_env()
        # The checkpointer needs autocommit and no prepared statements.
        async with AsyncConnectionPool(
            cfg.database_url,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
            open=False,
        ) as pool:
            checkpointer = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
            await checkpointer.setup()
            app.state.settings = cfg
            app.state.pool = pool
            app.state.graph = (graph_factory or _default_graph)(checkpointer)
            yield

    app = FastAPI(title="CareDesk API", lifespan=lifespan)

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        """Report whether the server and its database are up."""
        try:
            async with pool_of(request).connection() as conn:
                await conn.execute("SELECT 1")
        except Exception as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable."
            ) from error
        return {"status": "ok"}

    @app.post("/auth/login")
    async def login(request: Request, body: LoginRequest) -> TokenResponse:
        """Exchange email and password for a sign-in token."""
        cfg: Settings = request.app.state.settings
        account = await store.find_account_by_email(pool_of(request), body.email)
        if (
            not verify_password(
                account.password_hash if account else None, body.password
            )
            or account is None
        ):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Wrong email or password."
            )
        token = create_token(account.id, cfg.auth_secret, cfg.token_minutes)
        return TokenResponse(access_token=token, expires_in=cfg.token_minutes * 60)

    @app.get("/me")
    async def me(account: Signed) -> Profile:
        """Return the signed-in user."""
        return Profile(email=account.email, role=account.role, name=account.full_name)

    @app.post("/threads", status_code=status.HTTP_201_CREATED)
    async def new_thread(request: Request, account: Signed) -> ThreadOut:
        """Start a new conversation."""
        thread = await store.create_thread(pool_of(request), account.id)
        return ThreadOut(
            thread_id=thread.id, created_at=thread.created_at, title=thread.title
        )

    @app.get("/threads")
    async def threads(request: Request, account: Signed) -> list[ThreadOut]:
        """List the signed-in user's own conversations."""
        rows = await store.list_threads(pool_of(request), account.id)
        return [
            ThreadOut(thread_id=t.id, created_at=t.created_at, title=t.title)
            for t in rows
        ]

    @app.get("/threads/{thread_id}/messages")
    async def history(
        request: Request, account: Signed, thread_id: uuid.UUID
    ) -> list[MessageOut]:
        """Return the questions and answers in one of the user's conversations."""
        await require_thread(request, account, thread_id)
        graph: Graph = request.app.state.graph
        state = await graph.aget_state({"configurable": {"thread_id": str(thread_id)}})
        out: list[MessageOut] = []
        for m in state.values.get("messages", []):
            if isinstance(m, HumanMessage):
                out.append(MessageOut(role="user", content=m.text))
            elif isinstance(m, AIMessage) and m.text and not m.tool_calls:
                out.append(MessageOut(role="assistant", content=m.text))
        return out

    @app.post("/threads/{thread_id}/messages")
    async def chat(
        request: Request, account: Signed, thread_id: uuid.UUID, body: ChatRequest
    ) -> StreamingResponse:
        """Ask a question; the answer streams back as server-sent events.

        Events: `token` (a piece of the answer), then `done` (with the triage
        route), or `error`. Each request is recorded as usage and never blocked
        because of it (ADR-0009).
        """
        await require_thread(request, account, thread_id)
        await store.title_thread(pool_of(request), thread_id, _title(body.content))
        events = _answer(
            request.app.state.graph, pool_of(request), account, thread_id, body.content
        )
        return StreamingResponse(
            events,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    return app


async def _answer(
    graph: Graph,
    pool: store.Pool,
    account: store.Account,
    thread_id: uuid.UUID,
    content: str,
) -> AsyncIterator[str]:
    """Run the graph for one message and yield the answer as server-sent events."""
    started = time.monotonic()
    usage = UsageMetadataCallbackHandler()
    config: RunnableConfig = {
        "configurable": {"thread_id": str(thread_id)},
        "callbacks": [usage],
        "metadata": {
            "user_id": account.user_id,
            "role": account.role,
            "account_id": account.id,
            "thread_id": str(thread_id),
        },
    }
    route: str | None = None
    last_message_id: str | None = None
    try:
        async for part in graph.astream(
            {"messages": [HumanMessage(content)]},
            config,
            context=Context(user_id=account.user_id, role=account.role),
            stream_mode=["messages", "updates"],
            version="v2",
        ):
            if part["type"] == "messages":
                message, meta = part["data"]
                # Only the answering model streams to the user; triage output is internal.
                if (
                    meta.get("langgraph_node") == "agent"
                    and isinstance(message, AIMessage)
                    and message.text
                ):
                    # Text the model writes before calling a tool is a separate message.
                    if last_message_id not in (None, message.id):
                        yield _sse("token", {"text": "\n\n"})
                    last_message_id = message.id
                    yield _sse("token", {"text": message.text})
            elif part["type"] == "updates":
                for node, update in part["data"].items():
                    if not isinstance(update, dict):
                        continue
                    if node == "triage":
                        route = update.get("route")
                    elif node in FIXED_REPLY_NODES:
                        yield _sse("token", {"text": update["messages"][-1].text})
        yield _sse("done", {"route": route})
    except Exception:
        log.exception("Chat request failed for thread %s", thread_id)
        yield _sse("error", {"message": ERROR_REPLY})
    finally:
        tokens = usage.usage_metadata.values()
        try:
            await store.record_usage(
                pool,
                account.id,
                thread_id,
                route,
                sum(t.get("input_tokens", 0) for t in tokens),
                sum(t.get("output_tokens", 0) for t in tokens),
                int((time.monotonic() - started) * 1000),
            )
        except Exception:
            log.exception("Could not record usage for thread %s", thread_id)


def _default_graph(checkpointer: AsyncPostgresSaver) -> Graph:
    return build_graph(checkpointer=checkpointer)


app = create_app()
