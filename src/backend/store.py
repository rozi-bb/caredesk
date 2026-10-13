"""Queries for the app's own tables: accounts, threads, Telegram links, and usage.

The home's records are read only by the agent's tools (agent/records.py);
nothing here touches them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation
from psycopg_pool import AsyncConnectionPool

Pool = AsyncConnectionPool[AsyncConnection[dict[str, Any]]]
Channel = Literal["web", "telegram"]

_ACCOUNT_SELECT = """
    SELECT a.id, a.email, a.role, a.password_hash,
           COALESCE(a.staff_id, a.family_member_id) AS user_id,
           COALESCE(s.full_name, f.full_name) AS full_name
    FROM accounts a
    LEFT JOIN staff s ON s.id = a.staff_id
    LEFT JOIN family_members f ON f.id = a.family_member_id
"""


@dataclass(frozen=True)
class Account:
    """A signed-in user, and the identity the agent runs with."""

    id: int
    email: str
    role: Literal["staff", "family"]
    user_id: int
    full_name: str
    password_hash: str


@dataclass(frozen=True)
class TelegramLink:
    """The Telegram user an account is connected to."""

    telegram_user_id: int
    telegram_username: str | None
    linked_at: datetime


@dataclass(frozen=True)
class Thread:
    """A conversation owned by one account."""

    id: uuid.UUID
    created_at: datetime
    title: str | None = None


def _account(row: dict[str, Any] | None) -> Account | None:
    return Account(**row) if row else None


async def find_account_by_email(pool: Pool, email: str) -> Account | None:
    """Return the account with this email, ignoring case."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            _ACCOUNT_SELECT + " WHERE lower(a.email) = lower(%s)", (email.strip(),)
        )
        return _account(await cur.fetchone())


async def get_account(pool: Pool, account_id: int) -> Account | None:
    """Return the account with this id."""
    async with pool.connection() as conn:
        cur = await conn.execute(_ACCOUNT_SELECT + " WHERE a.id = %s", (account_id,))
        return _account(await cur.fetchone())


async def create_thread(
    pool: Pool, account_id: int, thread_id: uuid.UUID | None = None
) -> Thread | None:
    """Create a new conversation owned by the account.

    The client may choose the id (the chat UI uses its own). Returns None if
    that id is already taken, by anyone: an existing thread is never handed
    to another account.
    """
    async with pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO threads (id, account_id) VALUES (%s, %s) "
            "ON CONFLICT (id) DO NOTHING RETURNING id, created_at, title",
            (thread_id or uuid.uuid4(), account_id),
        )
        row = await cur.fetchone()
        return Thread(**row) if row else None


async def list_threads(pool: Pool, account_id: int) -> list[Thread]:
    """Return the account's conversations, newest first."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id, created_at, title FROM threads WHERE account_id = %s "
            "ORDER BY created_at DESC",
            (account_id,),
        )
        return [Thread(**row) for row in await cur.fetchall()]


async def owns_thread(pool: Pool, account_id: int, thread_id: uuid.UUID) -> bool:
    """Return True only if the thread exists and belongs to the account."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM threads WHERE id = %s AND account_id = %s",
            (thread_id, account_id),
        )
        return await cur.fetchone() is not None


async def delete_thread(pool: Pool, account_id: int, thread_id: uuid.UUID) -> None:
    """Delete one of the account's conversations; its usage rows are kept."""
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM threads WHERE id = %s AND account_id = %s",
            (thread_id, account_id),
        )


async def title_thread(pool: Pool, thread_id: uuid.UUID, title: str) -> None:
    """Give the thread a title, unless it already has one."""
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE threads SET title = %s WHERE id = %s AND title IS NULL",
            (title, thread_id),
        )


async def record_usage(
    pool: Pool,
    account_id: int,
    thread_id: uuid.UUID,
    route: str | None,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
    channel: Channel = "web",
) -> None:
    """Add one usage row for a chat request."""
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO usage_events (account_id, thread_id, route, input_tokens, "
            "output_tokens, duration_ms, channel) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                account_id,
                thread_id,
                route,
                input_tokens,
                output_tokens,
                duration_ms,
                channel,
            ),
        )


# ---------- Telegram (ADR-0027) ----------


async def create_link_code(
    pool: Pool, account_id: int, code_hash: str, minutes: int
) -> datetime:
    """Store a new connect code for the account and return when it expires.

    Any earlier code of the account stops working, and expired codes are
    cleared on the way.
    """
    async with pool.connection() as conn, conn.transaction():
        await conn.execute(
            "DELETE FROM telegram_link_codes WHERE account_id = %s OR expires_at <= now()",
            (account_id,),
        )
        cur = await conn.execute(
            "INSERT INTO telegram_link_codes (code_hash, account_id, expires_at) "
            "VALUES (%s, %s, now() + %s) RETURNING expires_at",
            (code_hash, account_id, timedelta(minutes=minutes)),
        )
        row = await cur.fetchone()
        assert row is not None
        expires_at: datetime = row["expires_at"]
        return expires_at


async def use_link_code(
    pool: Pool, code_hash: str, telegram_user_id: int, telegram_username: str | None
) -> Account | None:
    """Connect the Telegram user to the code's account and use the code up.

    Returns None if the code is unknown, expired, or already used. The code is
    checked and deleted in one statement, so two attempts with the same code
    can never both succeed. Any earlier link of this Telegram user or of this
    account is replaced.
    """
    try:
        async with pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                "DELETE FROM telegram_link_codes "
                "WHERE code_hash = %s AND expires_at > now() RETURNING account_id",
                (code_hash,),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            account_id: int = row["account_id"]
            await conn.execute(
                "DELETE FROM telegram_links "
                "WHERE telegram_user_id = %s OR account_id = %s",
                (telegram_user_id, account_id),
            )
            await conn.execute(
                "INSERT INTO telegram_links "
                "(account_id, telegram_user_id, telegram_username) VALUES (%s, %s, %s)",
                (account_id, telegram_user_id, telegram_username),
            )
    except UniqueViolation:
        # Another code linked the same Telegram user at the same moment; the
        # whole attempt is rolled back, code included.
        return None
    return await get_account(pool, account_id)


async def get_telegram_link(pool: Pool, account_id: int) -> TelegramLink | None:
    """Return the account's Telegram link, if it has one."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT telegram_user_id, telegram_username, linked_at "
            "FROM telegram_links WHERE account_id = %s",
            (account_id,),
        )
        row = await cur.fetchone()
        return TelegramLink(**row) if row else None


async def unlink_account(pool: Pool, account_id: int) -> None:
    """Disconnect the account from Telegram."""
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM telegram_links WHERE account_id = %s", (account_id,)
        )


async def unlink_telegram_user(pool: Pool, telegram_user_id: int) -> None:
    """Disconnect the Telegram user from whichever account it is linked to."""
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM telegram_links WHERE telegram_user_id = %s",
            (telegram_user_id,),
        )


async def find_account_by_telegram(pool: Pool, telegram_user_id: int) -> Account | None:
    """Return the account linked to the Telegram user, if any."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            _ACCOUNT_SELECT
            + " JOIN telegram_links t ON t.account_id = a.id"
            + " WHERE t.telegram_user_id = %s",
            (telegram_user_id,),
        )
        return _account(await cur.fetchone())


async def telegram_thread(pool: Pool, account_id: int) -> uuid.UUID | None:
    """Return the session that the account's Telegram messages continue."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT current_thread_id FROM telegram_links WHERE account_id = %s",
            (account_id,),
        )
        row = await cur.fetchone()
        return row["current_thread_id"] if row else None


async def set_telegram_thread(
    pool: Pool, account_id: int, thread_id: uuid.UUID | None
) -> None:
    """Set the session Telegram continues; None makes the next message start one."""
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE telegram_links SET current_thread_id = %s WHERE account_id = %s",
            (thread_id, account_id),
        )
