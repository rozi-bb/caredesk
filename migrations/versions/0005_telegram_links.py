"""Telegram accounts linked to CareDesk accounts, and the usage channel (ADR-0027).

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the Telegram link tables and record each request's channel."""
    op.execute(
        """
        -- One Telegram user per account and one account per Telegram user.
        -- current_thread_id is the session that Telegram messages continue.
        CREATE TABLE telegram_links (
            account_id        integer PRIMARY KEY REFERENCES accounts (id) ON DELETE CASCADE,
            telegram_user_id  bigint NOT NULL UNIQUE,
            telegram_username text,
            current_thread_id uuid REFERENCES threads (id) ON DELETE SET NULL,
            linked_at         timestamptz NOT NULL DEFAULT now()
        );

        -- One-time connect codes. Only a hash is stored, so the table cannot
        -- be used to connect even if it is read.
        CREATE TABLE telegram_link_codes (
            code_hash  text PRIMARY KEY,
            account_id integer NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
            expires_at timestamptz NOT NULL
        );
        CREATE INDEX telegram_link_codes_account ON telegram_link_codes (account_id);

        ALTER TABLE usage_events ADD COLUMN channel text NOT NULL DEFAULT 'web'
            CHECK (channel IN ('web', 'telegram'));
        """
    )


def downgrade() -> None:
    """Drop the Telegram tables and the usage channel."""
    op.execute(
        """
        ALTER TABLE usage_events DROP COLUMN channel;
        DROP TABLE telegram_link_codes, telegram_links;
        """
    )
