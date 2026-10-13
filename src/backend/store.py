"""Queries for the app's own tables: accounts, thread ownership, and usage.

The home's records are read only by the agent's tools (agent/records.py);
nothing here touches them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

Pool = AsyncConnectionPool[AsyncConnection[dict[str, Any]]]

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


async def create_thread(pool: Pool, account_id: int) -> Thread:
    """Create a new conversation owned by the account."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO threads (id, account_id) VALUES (%s, %s) "
            "RETURNING id, created_at, title",
            (uuid.uuid4(), account_id),
        )
        row = await cur.fetchone()
        assert row is not None
        return Thread(**row)


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
) -> None:
    """Add one usage row for a chat request."""
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO usage_events (account_id, thread_id, route, input_tokens, "
            "output_tokens, duration_ms) VALUES (%s, %s, %s, %s, %s, %s)",
            (account_id, thread_id, route, input_tokens, output_tokens, duration_ms),
        )
