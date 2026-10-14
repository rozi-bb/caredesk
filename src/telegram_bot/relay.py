"""What the bot replies to each command and message (ADR-0027).

Kept apart from the Telegram library so every reply can be tested without
Telegram. Replies are Markdown; `bot.py` converts them for Telegram.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator

import httpx

from telegram_bot.backend import BotBackend, InvalidCode, NotConnected

log = logging.getLogger(__name__)

MAX_MESSAGE = 4000  # the backend's limit for one message

# Only when the backend cannot be reached: the emergency line must still show.
UNREACHABLE = (
    "CareDesk is not reachable right now. Please try again in a moment.\n\n"
    "**In an emergency, press the call bell or call 911.**"
)
NOT_CONNECTED = (
    "Hi, I'm CareDesk, Evergreen Care Home's assistant.\n\n"
    "To chat with me, connect your account first: sign in on the CareDesk website "
    "and press **Connect Telegram**.\n\n**{emergency_notice}**"
)
CONNECTED = "Hi {name}, this Telegram is now connected to CareDesk. {topics}"
HELP = "You are connected as {name}. {topics}"
COMMANDS = "/new starts a new conversation\n/disconnect disconnects this Telegram"
INVALID_LINK = (
    "This link is invalid or has expired. Get a new one on the CareDesk website "
    "with **Connect Telegram**."
)
NEW_SESSION = "Started a new conversation. Earlier ones are in the sidebar on the CareDesk website."
DISCONNECTED = (
    "This Telegram is disconnected from CareDesk. To connect again, use "
    "**Connect Telegram** on the website."
)
TOO_LONG = f"That message is too long. Please keep it under {MAX_MESSAGE} characters."
TEXT_ONLY = "I can only read text messages."
CUT_OFF = "The answer was cut off. Please ask again."


class Relay:
    """Turns Telegram events into backend calls and replies."""

    def __init__(self, backend: BotBackend):
        """Use this backend for every call."""
        self._backend = backend
        # One request at a time per user keeps their conversation in order;
        # different users never wait for each other, so an emergency is not queued.
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def _not_connected(self) -> str:
        try:
            texts = await self._backend.texts()
        except httpx.HTTPError:
            return UNREACHABLE
        return NOT_CONNECTED.format(emergency_notice=texts.emergency_notice)

    async def start(
        self, telegram_user_id: int, username: str | None, code: str | None
    ) -> str:
        """Reply to /start, which carries the connect code when opened from the link."""
        try:
            if code is None:
                return await self.help(telegram_user_id)
            async with self._locks[telegram_user_id]:
                name = await self._backend.connect(code, telegram_user_id, username)
            texts = await self._backend.texts()
            welcome = CONNECTED.format(name=name, topics=texts.topics)
            return f"{welcome}\n\n{COMMANDS}\n\n**{texts.emergency_notice}**"
        except InvalidCode:
            return INVALID_LINK
        except httpx.HTTPError:
            log.exception("Backend unreachable")
            return UNREACHABLE

    async def help(self, telegram_user_id: int) -> str:
        """Reply to /help: who you are connected as, or how to connect."""
        try:
            name = await self._backend.whoami(telegram_user_id)
            texts = await self._backend.texts()
            return (
                f"{HELP.format(name=name, topics=texts.topics)}\n\n{COMMANDS}\n\n"
                f"**{texts.emergency_notice}**"
            )
        except NotConnected:
            return await self._not_connected()
        except httpx.HTTPError:
            log.exception("Backend unreachable")
            return UNREACHABLE

    async def new(self, telegram_user_id: int) -> str:
        """Reply to /new."""
        try:
            async with self._locks[telegram_user_id]:
                await self._backend.new_session(telegram_user_id)
            return NEW_SESSION
        except NotConnected:
            return await self._not_connected()
        except httpx.HTTPError:
            log.exception("Backend unreachable")
            return UNREACHABLE

    async def disconnect(self, telegram_user_id: int) -> str:
        """Reply to /disconnect."""
        try:
            async with self._locks[telegram_user_id]:
                await self._backend.disconnect(telegram_user_id)
            return DISCONNECTED
        except httpx.HTTPError:
            log.exception("Backend unreachable")
            return UNREACHABLE

    async def stream(self, telegram_user_id: int, text: str) -> AsyncIterator[str]:
        """Answer a text message as the connected account, piece by piece."""
        if len(text) > MAX_MESSAGE:
            yield TOO_LONG
            return
        answered = False
        try:
            async with self._locks[telegram_user_id]:
                async for piece in self._backend.ask(telegram_user_id, text):
                    answered = True
                    yield piece
        except NotConnected:
            yield await self._not_connected()
        except httpx.HTTPError:
            log.exception("Backend unreachable")
            yield f"\n\n{CUT_OFF}" if answered else UNREACHABLE

    async def message(self, telegram_user_id: int, text: str) -> str:
        """Answer a text message as the connected account, all at once."""
        return "".join([piece async for piece in self.stream(telegram_user_id, text)])
