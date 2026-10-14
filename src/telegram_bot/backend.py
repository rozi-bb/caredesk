"""HTTP client for the CareDesk backend, used by the Telegram bot (ADR-0027).

The bot never calls a model or the database. It proves itself to the backend
with its own key and says which Telegram user a request is about; the backend
decides which account, if any, that is.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

# Answers take as long as the model needs; only connecting is time-limited.
TIMEOUT = httpx.Timeout(10.0, read=180.0)


class NotConnected(Exception):
    """The Telegram user has not connected a CareDesk account."""


class InvalidCode(Exception):
    """The connect code is unknown, expired, or already used."""


class BotKeyRejected(Exception):
    """The backend refused the bot's key: TELEGRAM_BOT_KEY differs between the two .env files."""


@dataclass(frozen=True)
class Texts:
    """Fixed texts from the backend: what to ask, and the emergency contacts."""

    topics: str
    emergency_notice: str


class BotBackend:
    """Calls the backend's bot endpoints."""

    def __init__(
        self,
        base_url: str,
        bot_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        """Point the client at the backend; tests pass an in-process transport."""
        self._base_url = base_url.rstrip("/")
        self._bot_key = bot_key
        self._transport = transport

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            transport=self._transport,
            timeout=TIMEOUT,
            headers={"X-Bot-Key": self._bot_key},
        )

    @staticmethod
    def _check(response: httpx.Response) -> None:
        if response.status_code == 401:
            raise BotKeyRejected
        if response.status_code == 403:
            raise NotConnected
        response.raise_for_status()

    async def _post(self, path: str, body: dict[str, object]) -> httpx.Response:
        async with self._http() as http:
            response = await http.post(path, json=body)
        return response

    async def texts(self) -> Texts:
        """Return the fixed texts every client shows."""
        async with self._http() as http:
            response = await http.get("/texts")
        response.raise_for_status()
        return Texts(**response.json())

    async def connect(
        self, code: str, telegram_user_id: int, telegram_username: str | None
    ) -> str:
        """Connect the Telegram user with a code; return the account holder's name."""
        response = await self._post(
            "/telegram/connect",
            {
                "code": code,
                "telegram_user_id": telegram_user_id,
                "telegram_username": telegram_username,
            },
        )
        if response.status_code in (400, 422):
            raise InvalidCode
        self._check(response)
        name: str = response.json()["name"]
        return name

    async def whoami(self, telegram_user_id: int) -> str:
        """Return the name of the account the Telegram user is connected to."""
        response = await self._post(
            "/telegram/me", {"telegram_user_id": telegram_user_id}
        )
        self._check(response)
        name: str = response.json()["name"]
        return name

    async def new_session(self, telegram_user_id: int) -> None:
        """Make the user's next message start a new conversation."""
        response = await self._post(
            "/telegram/new", {"telegram_user_id": telegram_user_id}
        )
        self._check(response)

    async def disconnect(self, telegram_user_id: int) -> None:
        """Disconnect the Telegram user from their account."""
        response = await self._post(
            "/telegram/disconnect", {"telegram_user_id": telegram_user_id}
        )
        self._check(response)

    async def ask(self, telegram_user_id: int, content: str) -> AsyncIterator[str]:
        """Send a message and yield the answer piece by piece as the backend streams it.

        Raises NotConnected before yielding anything if the user has not connected.
        """
        async with (
            self._http() as http,
            http.stream(
                "POST",
                "/telegram/messages",
                json={"telegram_user_id": telegram_user_id, "content": content},
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
                    if text := _answer_text(block):
                        yield text


def _answer_text(block: str) -> str | None:
    """Return the answer text in one server-sent event, if it carries any."""
    fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
    data = json.loads(fields.get("data", "{}"))
    if fields.get("event") == "token":
        text: str = data["text"]
        return text
    if fields.get("event") == "error":
        message: str = data["message"]
        return message
    return None
