"""Backend settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from agent.db import database_url

MIN_SECRET_LENGTH = 32
_GENERATE = (
    "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
)


@dataclass(frozen=True)
class Settings:
    """Everything the backend needs from its environment."""

    database_url: str
    auth_secret: str
    token_minutes: int = 8 * 60
    # The Telegram channel is off unless both are set (ADR-0027).
    telegram_bot_username: str | None = None
    telegram_bot_key: str | None = None

    @property
    def telegram_enabled(self) -> bool:
        """True when the Telegram bot can connect accounts and chat."""
        return bool(self.telegram_bot_username and self.telegram_bot_key)

    @classmethod
    def from_env(cls) -> Settings:
        """Read settings, refusing to start with a weak secret."""
        secret = os.environ.get("AUTH_SECRET", "")
        if len(secret) < MIN_SECRET_LENGTH:
            raise RuntimeError(
                f"AUTH_SECRET must be set to at least {MIN_SECRET_LENGTH} characters. "
                f"{_GENERATE}"
            )
        bot_key = os.environ.get("TELEGRAM_BOT_KEY", "")
        if bot_key and len(bot_key) < MIN_SECRET_LENGTH:
            raise RuntimeError(
                f"TELEGRAM_BOT_KEY must be at least {MIN_SECRET_LENGTH} characters. "
                f"{_GENERATE}"
            )
        username = os.environ.get("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
        return cls(
            database_url=database_url(),
            auth_secret=secret,
            token_minutes=int(os.environ.get("AUTH_TOKEN_MINUTES", str(8 * 60))),
            telegram_bot_username=username or None,
            telegram_bot_key=bot_key or None,
        )
