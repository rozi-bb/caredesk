"""Keep usage records when a conversation is deleted.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Let usage outlive its thread: cost per user must not change when a user deletes a chat."""
    op.execute(
        """
        ALTER TABLE usage_events ALTER COLUMN thread_id DROP NOT NULL;
        ALTER TABLE usage_events DROP CONSTRAINT usage_events_thread_id_fkey;
        ALTER TABLE usage_events ADD CONSTRAINT usage_events_thread_id_fkey
            FOREIGN KEY (thread_id) REFERENCES threads (id) ON DELETE SET NULL;
        """
    )


def downgrade() -> None:
    """Restore the original constraint (fails if usage rows lost their thread)."""
    op.execute(
        """
        ALTER TABLE usage_events DROP CONSTRAINT usage_events_thread_id_fkey;
        ALTER TABLE usage_events ADD CONSTRAINT usage_events_thread_id_fkey
            FOREIGN KEY (thread_id) REFERENCES threads (id);
        ALTER TABLE usage_events ALTER COLUMN thread_id SET NOT NULL;
        """
    )
