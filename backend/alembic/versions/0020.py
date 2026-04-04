"""add user deletion request tracking

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-04

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "deletion_requested_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when user requested account deletion (soft delete)"
        ),
    )
    op.create_index(
        op.f("ix_users_deletion_requested_at"),
        "users",
        ["deletion_requested_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_users_deletion_requested_at"), table_name="users")
    op.drop_column("users", "deletion_requested_at")
