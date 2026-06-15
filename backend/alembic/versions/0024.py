"""add registration request review metadata

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-15

"""

import sqlalchemy as sa

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "registration_requests",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "registration_requests",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("registration_requests", "rejection_reason")
    op.drop_column("registration_requests", "reviewed_at")
