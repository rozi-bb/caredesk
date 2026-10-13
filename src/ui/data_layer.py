"""Chainlit data layer that reads conversations from the backend (ADR-0025).

It powers Chainlit's sidebar of past conversations without storing anything
itself: the backend stays the only place conversations live. Ownership is
always learned from the backend with the owner's own token, and anything
not learned that way is treated as not found.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from chainlit.data.base import BaseDataLayer
from chainlit.step import StepDict
from chainlit.types import (
    Feedback,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import PersistedUser, User

from ui.client import BackendClient, ConversationNotFound, SignInRequired


@dataclass
class _KnownThread:
    owner: str
    created_at: str
    title: str | None


class BackendDataLayer(BaseDataLayer):
    """Sidebar history backed by the CareDesk API. Writes are the backend's job."""

    def __init__(self, backend: BackendClient):
        """Keep the client; tokens and thread owners are learned as users sign in."""
        self._backend = backend
        self._tokens: dict[str, str] = {}
        self._threads: dict[str, _KnownThread] = {}

    # ---------- users ----------

    def token_for(self, identifier: str) -> str | None:
        """Return the backend token of a signed-in user."""
        return self._tokens.get(identifier)

    async def get_user(self, identifier: str) -> PersistedUser | None:
        """Never return a stored user, so Chainlit always passes its signed-in user to create_user.

        Accounts live in the backend. This way the backend token, which sits
        in Chainlit's signed session cookie, is picked up again on every
        request, even after the UI restarts.
        """
        return None

    async def create_user(self, user: User) -> PersistedUser | None:
        """Remember the user's backend token and return the user without it."""
        if token := user.metadata.get("token"):
            self._tokens[user.identifier] = token
        return PersistedUser(
            id=user.identifier,
            identifier=user.identifier,
            display_name=user.display_name,
            metadata={"role": user.metadata.get("role")},
            createdAt=datetime.now(UTC).isoformat(),
        )

    # ---------- threads ----------

    def remember_thread(self, thread_id: str, owner: str, title: str | None) -> None:
        """Record a thread the owner just created through the backend."""
        self._threads[thread_id] = _KnownThread(
            owner, datetime.now(UTC).isoformat(), title
        )

    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        """List the signed-in user's conversations. Chainlit sets userId to the current user."""
        owner = filters.userId or ""
        token = self._tokens.get(owner)
        threads = []
        if token:
            try:
                threads = await self._backend.threads(token)
            except (SignInRequired, httpx.HTTPError):
                threads = []
        for t in threads:
            self._threads[t.id] = _KnownThread(owner, t.created_at, t.title)
        visible = [t for t in threads if t.title]
        if filters.search:
            visible = [
                t for t in visible if filters.search.lower() in (t.title or "").lower()
            ]
        ids = [t.id for t in visible]
        start = ids.index(pagination.cursor) + 1 if pagination.cursor in ids else 0
        page = visible[start : start + pagination.first]
        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=start + pagination.first < len(visible),
                startCursor=page[0].id if page else None,
                endCursor=page[-1].id if page else None,
            ),
            data=[
                self._thread_dict(t.id, owner, t.created_at, t.title, []) for t in page
            ],
        )

    async def get_thread_author(self, thread_id: str) -> str:
        """Return the owner, or "" (not found) if the backend has not confirmed one."""
        known = self._threads.get(thread_id)
        return known.owner if known else ""

    async def get_thread(self, thread_id: str) -> ThreadDict | None:
        """Load a conversation's messages from the backend with its owner's token."""
        known = self._threads.get(thread_id)
        token = self._tokens.get(known.owner) if known else None
        if not known or not token:
            return None
        try:
            history = await self._backend.history(token, thread_id)
        except (SignInRequired, ConversationNotFound):
            return None
        started = datetime.fromisoformat(known.created_at)
        steps: list[StepDict] = []
        for i, (role, content) in enumerate(history):
            # Messages carry no times of their own; spacing keeps them in order.
            at = (started + timedelta(milliseconds=i)).isoformat()
            steps.append(
                {
                    "id": f"{thread_id}-{i}",
                    "threadId": thread_id,
                    "parentId": None,
                    "name": known.owner if role == "user" else "CareDesk",
                    "type": "user_message" if role == "user" else "assistant_message",
                    "input": "",
                    "output": content,
                    "createdAt": at,
                    "start": at,
                    "end": at,
                    "streaming": False,
                    "isError": False,
                    "metadata": {},
                }
            )
        return self._thread_dict(
            thread_id, known.owner, known.created_at, known.title, steps
        )

    async def delete_thread(self, thread_id: str) -> None:
        """Delete through the backend, which checks ownership again."""
        known = self._threads.pop(thread_id, None)
        token = self._tokens.get(known.owner) if known else None
        if token:
            try:
                await self._backend.delete_thread(token, thread_id)
            except ConversationNotFound:
                pass

    async def update_thread(
        self,
        thread_id: str,
        name: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Ignore: the backend names threads by their first question."""

    @staticmethod
    def _thread_dict(
        thread_id: str,
        owner: str,
        created_at: str,
        title: str | None,
        steps: list[StepDict],
    ) -> ThreadDict:
        return {
            "id": thread_id,
            "createdAt": created_at,
            "name": title,
            "userId": owner,
            "userIdentifier": owner,
            "tags": [],
            "metadata": {},
            "steps": steps,
            "elements": [],
        }

    # ---------- not used: messages, files, and feedback are not stored by the UI ----------

    async def create_step(self, step_dict: StepDict) -> None:
        """Ignore: the backend stores every message."""

    async def update_step(self, step_dict: StepDict) -> None:
        """Ignore: the backend stores every message."""

    async def delete_step(self, step_id: str) -> None:
        """Ignore: messages cannot be edited or deleted."""

    async def create_element(self, element: Any) -> None:
        """Ignore: file upload is off."""

    async def get_element(self, thread_id: str, element_id: str) -> None:
        """Nothing is stored."""
        return None

    async def delete_element(
        self, element_id: str, thread_id: str | None = None
    ) -> None:
        """Ignore: file upload is off."""

    async def upsert_feedback(self, feedback: Feedback) -> str:
        """Ignore: feedback is not collected yet."""
        return ""

    async def delete_feedback(self, feedback_id: str) -> bool:
        """Ignore: feedback is not collected yet."""
        return True

    async def get_favorite_steps(self, user_id: str) -> list[StepDict]:
        """Favorites are off."""
        return []

    async def build_debug_url(self) -> str:
        """No debug view."""
        return ""

    async def close(self) -> None:
        """Nothing to close: each backend call opens its own connection."""
