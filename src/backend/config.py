"""Backend settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from agent.db import database_url

MIN_SECRET_LENGTH = 32


@dataclass(frozen=True)
class Settings:
    """Everything the backend needs from its environment."""

    database_url: str
    auth_secret: str
    token_minutes: int = 8 * 60

    @classmethod
    def from_env(cls) -> Settings:
        """Read settings, refusing to start without a strong signing secret."""
        secret = os.environ.get("AUTH_SECRET", "")
        if len(secret) < MIN_SECRET_LENGTH:
            raise RuntimeError(
                f"AUTH_SECRET must be set to at least {MIN_SECRET_LENGTH} characters. "
                "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
            )
        return cls(
            database_url=database_url(),
            auth_secret=secret,
            token_minutes=int(os.environ.get("AUTH_TOKEN_MINUTES", str(8 * 60))),
        )
