"""HTTP client for the CareDesk backend, used by the chat UI.

The UI never calls a model or the database: everything goes through these
calls, with the signed-in user's token (ADR-0024).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

# Chat answers stream for as long as the model takes; only connecting is time-limited.
TIMEOUT = httpx.Timeout(10.0, read=180.0)


class SignInRequired(Exception):
    """The token is missing, invalid, or expired."""


class ConversationNotFound(Exception):
    """The conversation does not exist or belongs to someone else."""


class ThreadIdTaken(Exception):
    """The chosen conversation id is already in use."""


@dataclass(frozen=True)
class Profile:
    """The signed-in user."""

    email: str
    role: str
    name: str


@dataclass(frozen=True)
class Thread:
    """One of the user's conversations."""

    id: str
    title: str | None
    created_at: str


class BackendClient:
    """Calls the backend API. Each method takes the user's token."""

    def __init__(
        self, base_url: str, transport: httpx.AsyncBaseTransport | None = None
    ):
        """Point the client at the backend; tests pass an in-process transport."""
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url, transport=self._transport, timeout=TIMEOUT
        )

    @staticmethod
    def _auth(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _check(response: httpx.Response) -> None:
        if response.status_code == 401:
            raise SignInRequired
        if response.status_code == 404:
            raise ConversationNotFound
        response.raise_for_status()

    async def login(self, email: str, password: str) -> str | None:
        """Return a token, or None if the email or password is wrong."""
        async with self._http() as http:
            response = await http.post(
                "/auth/login", json={"email": email, "password": password}
            )
        if response.status_code in (401, 422):
            return None
        response.raise_for_status()
        token: str = response.json()["access_token"]
        return token

    async def profile(self, token: str) -> Profile:
        """Return who the token belongs to."""
        async with self._http() as http:
            response = await http.get("/me", headers=self._auth(token))
        self._check(response)
        return Profile(**response.json())

    async def threads(self, token: str) -> list[Thread]:
        """Return the user's conversations, newest first."""
        async with self._http() as http:
            response = await http.get("/threads", headers=self._auth(token))
        self._check(response)
        return [
            Thread(id=t["thread_id"], title=t["title"], created_at=t["created_at"])
            for t in response.json()
        ]

    async def new_thread(self, token: str, thread_id: str | None = None) -> str:
        """Start a conversation, optionally with a chosen id, and return its id."""
        async with self._http() as http:
            response = await http.post(
                "/threads",
                headers=self._auth(token),
                json={"thread_id": thread_id} if thread_id else None,
            )
        if response.status_code == 409:
            raise ThreadIdTaken
        self._check(response)
        created: str = response.json()["thread_id"]
        return created

    async def delete_thread(self, token: str, thread_id: str) -> None:
        """Delete one of the user's conversations."""
        async with self._http() as http:
            response = await http.delete(
                f"/threads/{thread_id}", headers=self._auth(token)
            )
        self._check(response)

    async def history(self, token: str, thread_id: str) -> list[tuple[str, str]]:
        """Return (role, content) pairs of one conversation."""
        async with self._http() as http:
            response = await http.get(
                f"/threads/{thread_id}/messages", headers=self._auth(token)
            )
        self._check(response)
        return [(m["role"], m["content"]) for m in response.json()]

    async def ask(
        self, token: str, thread_id: str, content: str
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Send a question and yield the server-sent events of the answer."""
        async with (
            self._http() as http,
            http.stream(
                "POST",
                f"/threads/{thread_id}/messages",
                headers=self._auth(token),
                json={"content": content},
            ) as response,
        ):
            if response.status_code != 200:
                await response.aread()
                self._check(response)
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    yield _parse_event(block)


def _parse_event(block: str) -> tuple[str, dict[str, Any]]:
    fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
    return fields.get("event", "message"), json.loads(fields.get("data", "{}"))
