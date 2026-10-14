"""Showing an answer in Telegram while it is being written (ADR-0028).

The answer so far is shown as a message draft, a temporary preview that
Telegram animates. Finished parts, and the whole answer at the end, are sent
as normal messages, which are what stays in the chat. Kept apart from the
Telegram library so it can be tested without Telegram.
"""

from __future__ import annotations

import logging
import secrets
import time
from collections.abc import Awaitable, Callable

from telegram_bot import format as tg_format

log = logging.getLogger(__name__)

DRAFT_EVERY = 1.0  # seconds between draft updates, within Telegram's rate limits

Draft = Callable[[int, str], Awaitable[object]]
Send = Callable[[str], Awaitable[object]]


def _new_draft_id() -> int:
    return secrets.randbelow(2**31 - 1) + 1  # Telegram needs a non-zero id


class AnswerStream:
    """One answer: a draft that grows, then the messages that stay."""

    def __init__(
        self,
        draft: Draft,
        send: Send,
        every: float = DRAFT_EVERY,
        clock: Callable[[], float] = time.monotonic,
    ):
        """Show drafts with `draft(draft_id, text)` and send messages with `send(text)`."""
        self._draft = draft
        self._send = send
        self._every = every
        self._clock = clock
        self._draft_id = _new_draft_id()
        self._sent = 0  # parts already sent as messages
        self._last_draft: float | None = None
        self._drafting = True

    async def update(self, answer_so_far: str) -> None:
        """Show the answer so far; send any part that is already complete."""
        parts = tg_format.split(answer_so_far)
        while len(parts) - 1 > self._sent:
            await self._send(parts[self._sent])
            self._sent += 1
            self._draft_id = _new_draft_id()
            self._last_draft = None
        now = self._clock()
        if not self._drafting or (
            self._last_draft is not None and now - self._last_draft < self._every
        ):
            return
        self._last_draft = now
        try:
            await self._draft(self._draft_id, parts[-1])
        except Exception:
            # Drafts are only a preview: if Telegram refuses one, stop drafting
            # this answer and rely on the final message, which always goes out.
            log.warning(
                "Draft refused; sending the answer when complete", exc_info=True
            )
            self._drafting = False

    async def finish(self, answer: str) -> None:
        """Send whatever has not been sent yet as normal messages."""
        for part in tg_format.split(answer)[self._sent :]:
            if part.strip():
                await self._send(part)
