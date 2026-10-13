"""Thread titles, so users can recognise an earlier conversation.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add a title, taken from the conversation's first message."""
    op.execute("ALTER TABLE threads ADD COLUMN title text")


def downgrade() -> None:
    """Remove the title."""
    op.execute("ALTER TABLE threads DROP COLUMN title")
